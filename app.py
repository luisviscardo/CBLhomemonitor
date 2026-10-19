import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from config import load_config, save_config, RouterConfig
from mikrotik_client import MikroTikClient
from mock_data import get_mock_snapshot, mock_ping
from database import (
    init_db,
    get_daily_history,
    get_monthly_history,
    get_device_consumption_ranking,
    record_traffic_sample
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mikrotik-monitor")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Inicializar banco de dados SQLite com histórico
init_db()

app = FastAPI(title="CBLhomemonitor API", version="1.0.0")

# Montar arquivos estáticos
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

current_config = load_config()
client = MikroTikClient(current_config)

class ConfigUpdateRequest(BaseModel):
    router_ip: str
    port: int = 80
    use_https: bool = False
    verify_ssl: bool = False
    username: str = "admin"
    password: str = ""
    wan_interface: str = "ether1"
    poll_interval: float = 2.0
    demo_mode: bool = False

    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_temp_threshold: float = 60.0
    telegram_notify_wan_down: bool = True
    telegram_notify_temp_high: bool = True

class TelegramTestRequest(BaseModel):
    bot_token: str
    chat_id: str

class PingRequest(BaseModel):
    address: str = "8.8.8.8"
    count: int = 4

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Carregando Dashboard MikroTik...</h1>")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/config")
async def get_current_configuration():
    cfg = current_config.model_dump()
    cfg["password_set"] = bool(cfg.get("password"))
    cfg["password"] = "••••••••" if cfg.get("password") else ""
    return cfg

@app.post("/api/config")
async def update_configuration(new_cfg: ConfigUpdateRequest):
    global current_config, client
    password_to_use = new_cfg.password
    if password_to_use == "••••••••" or not password_to_use:
        password_to_use = current_config.password

    token_to_use = new_cfg.telegram_bot_token.strip()
    if token_to_use == "••••••••" or (not token_to_use and current_config.telegram_bot_token):
        token_to_use = current_config.telegram_bot_token

    updated = RouterConfig(
        router_ip=new_cfg.router_ip.strip(),
        port=new_cfg.port,
        use_https=new_cfg.use_https,
        verify_ssl=new_cfg.verify_ssl,
        username=new_cfg.username.strip(),
        password=password_to_use,
        wan_interface=new_cfg.wan_interface.strip(),
        poll_interval=max(1.0, new_cfg.poll_interval),
        demo_mode=new_cfg.demo_mode,
        telegram_enabled=new_cfg.telegram_enabled,
        telegram_bot_token=token_to_use,
        telegram_chat_id=new_cfg.telegram_chat_id.strip(),
        telegram_temp_threshold=new_cfg.telegram_temp_threshold,
        telegram_notify_wan_down=new_cfg.telegram_notify_wan_down,
        telegram_notify_temp_high=new_cfg.telegram_notify_temp_high
    )

    save_config(updated)
    current_config = updated
    client = MikroTikClient(current_config)

    connection_test = None
    if not current_config.demo_mode:
        connection_test = await client.test_connection()

    return {
        "status": "success",
        "message": "Configurações atualizadas com sucesso!",
        "connection_test": connection_test,
        "demo_mode": current_config.demo_mode
    }

@app.post("/api/test-connection")
async def test_connection_endpoint(test_cfg: ConfigUpdateRequest):
    pwd = test_cfg.password
    if pwd == "••••••••" or not pwd:
        pwd = current_config.password

    temp_cfg = RouterConfig(
        router_ip=test_cfg.router_ip.strip(),
        port=test_cfg.port,
        use_https=test_cfg.use_https,
        verify_ssl=test_cfg.verify_ssl,
        username=test_cfg.username.strip(),
        password=pwd
    )
    temp_client = MikroTikClient(temp_cfg)
    result = await temp_client.test_connection()
    return result

@app.get("/api/status")
async def get_status():
    if current_config.demo_mode:
        data = get_mock_snapshot()
        data["mode"] = "demo"
        process_traffic_accounting(data)
        return data

    try:
        data = await client.get_full_snapshot()
        data["mode"] = "live"
        process_traffic_accounting(data)
        return data
    except Exception as e:
        logger.warning(f"Falha ao conectar com o MikroTik real: {e}. Alternando temporariamente para dados mockados.")
        data = get_mock_snapshot()
        data["mode"] = "fallback"
        data["error"] = f"Não foi possível contactar {current_config.router_ip}: {str(e)}"
        process_traffic_accounting(data)
        return data

@app.get("/api/history/daily")
async def api_daily_history(days: int = 30):
    """Retorna histórico de consumo diário nos últimos N dias"""
    return get_daily_history(days=min(90, max(7, days)))

@app.get("/api/history/monthly")
async def api_monthly_history(months: int = 12):
    """Retorna histórico de consumo mensal nos últimos N meses"""
    return get_monthly_history(months=min(24, max(3, months)))

@app.get("/api/history/hardware")
async def api_hardware_history(timeframe: str = "1h"):
    """Retorna o histórico de telemetria de hardware (CPU, RAM, Temperatura, Voltagem)"""
    from database import get_hardware_history
    if timeframe not in ["1h", "6h", "24h"]:
        timeframe = "1h"
    return get_hardware_history(timeframe=timeframe)

@app.get("/api/consumption/devices")
async def api_device_consumption(period: str = "month"):
    """Retorna o ranking e proporção de consumo por dispositivo (today, 7days, month)"""
    if period not in ["today", "7days", "month"]:
        period = "month"
    return get_device_consumption_ranking(period=period)

@app.post("/api/history/clear")
async def api_clear_history():
    """Limpa todo o histórico anterior e inicializa o registro limpo a partir de hoje."""
    from database import clear_all_history
    clear_all_history()
    return {
        "status": "success",
        "message": "Todo o histórico anterior foi excluído. O monitoramento agora registra a partir de hoje."
    }

# Rastreamento de deltas de tráfego e telemetria de hardware
prev_wan_rx = 0
prev_wan_tx = 0
last_hw_sample_time = 0.0

def process_traffic_accounting(data: dict):
    global prev_wan_rx, prev_wan_tx, last_hw_sample_time
    import time
    from database import record_hardware_sample

    now = time.time()

    # 1. Telemetria de Hardware (amostrada a cada 5 segundos)
    if now - last_hw_sample_time >= 4.5:
        sys = data.get("system", {})
        try:
            cpu_val = float(sys.get("cpu_load", 0))
            mem_pct = float(sys.get("memory_usage_pct", 0))
            free_mb = float(sys.get("free_memory", 0)) / (1024 * 1024)
            temp = float(sys.get("temperature", 42.0) or 42.0)
            volt = float(sys.get("voltage", 24.0) or 24.0)
            record_hardware_sample(cpu_val, mem_pct, free_mb, temp, volt)
            last_hw_sample_time = now
        except Exception as e:
            logger.debug(f"Erro ao salvar amostra de hardware: {e}")

    # 2. Contabilização de tráfego WAN e dispositivos
    traffic = data.get("traffic", {})
    curr_rx = traffic.get("total_rx_bytes", 0)
    curr_tx = traffic.get("total_tx_bytes", 0)

    if prev_wan_rx > 0 and (curr_rx >= prev_wan_rx and curr_tx >= prev_wan_tx):
        delta_rx = curr_rx - prev_wan_rx
        delta_tx = curr_tx - prev_wan_tx

        if delta_rx > 0 or delta_tx > 0:
            devices = data.get("devices", [])
            dev_deltas = []
            if devices:
                num_devs = len(devices)
                part_rx = delta_rx // num_devs
                part_tx = delta_tx // num_devs
                for dev in devices:
                    dev_deltas.append({
                        "mac_address": dev.get("mac-address") or dev.get("mac_address"),
                        "ip_address": dev.get("address") or dev.get("ip_address"),
                        "hostname": dev.get("hostname", "Dispositivo"),
                        "device_type": dev.get("type", "device"),
                        "rx_bytes": part_rx,
                        "tx_bytes": part_tx
                    })
            record_traffic_sample(delta_rx, delta_tx, dev_deltas)

    prev_wan_rx = curr_rx
    prev_wan_tx = curr_tx

    # 3. Verificação de Alertas no Telegram (Queda de Link e Alta Temperatura)
    if current_config.telegram_enabled:
        try:
            asyncio.create_task(telegram_alert_manager.check_alerts(current_config, data))
        except Exception as e:
            logger.debug(f"Erro ao verificar alertas Telegram: {e}")


from telegram_notifier import TelegramAlertManager, send_telegram_message

telegram_alert_manager = TelegramAlertManager()

@app.post("/api/telegram/test")
async def api_telegram_test(req: TelegramTestRequest):
    """Envia uma mensagem de teste imediata para verificar as credenciais do Telegram."""
    import time
    token = req.bot_token.strip() or current_config.telegram_bot_token
    chat_id = req.chat_id.strip() or current_config.telegram_chat_id
    if not token or not chat_id:
        return {"success": False, "error": "Informe o Bot Token e o Chat ID para testar."}

    test_msg = (
        "🚀 *CBLhomemonitor - Teste de Notificação!*\n\n"
        "Seu bot do Telegram foi configurado com sucesso para o monitor de rede residencial MikroTik.\n\n"
        "🔔 *Alertas Monitorados:*\n"
        f"• Queda e Restabelecimento do Link WAN\n"
        f"• Superaquecimento do Hardware (Limite: {current_config.telegram_temp_threshold}°C)\n\n"
        f"⏰ _Envio realizado em {time.strftime('%d/%m/%Y às %H:%M:%S')}_"
    )
    res = await send_telegram_message(token, chat_id, test_msg)
    return res

@app.post("/api/ping")
async def ping_endpoint(req: PingRequest):
    if current_config.demo_mode:
        return mock_ping(req.address, req.count)
    try:
        res = await client.ping(req.address, req.count)
        if "error" in res:
            return mock_ping(req.address, req.count)
        return res
    except Exception as e:
        return mock_ping(req.address, req.count)

@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("Cliente WebSocket conectado ao stream de monitoramento")
    try:
        while True:
            if current_config.demo_mode:
                data = get_mock_snapshot()
                data["mode"] = "demo"
            else:
                try:
                    data = await client.get_full_snapshot()
                    data["mode"] = "live"
                except Exception as e:
                    data = get_mock_snapshot()
                    data["mode"] = "fallback"
                    data["error"] = str(e)

            process_traffic_accounting(data)
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(current_config.poll_interval)
    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado")
    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}")

