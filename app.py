import asyncio
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Set, Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from config import load_config, save_config, RouterConfig, MikroTikDevice, get_app_dir, CONFIG_FILE
from mikrotik_client import MikroTikClient
from mock_data import get_mock_snapshot, mock_ping
from database import (
    init_db,
    clear_all_history,
    get_daily_history,
    get_monthly_history,
    get_device_consumption_ranking,
    record_traffic_sample,
    sync_device_baseline
)
from telegram_notifier import TelegramAlertManager, send_telegram_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CBLhomemonitor")

def get_resource_dir() -> Path:
    """Localiza recursos estáticos e templates mesmo dentro do bundle PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

BASE_DIR = get_resource_dir()
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Inicializar banco de dados SQLite com histórico
init_db()

current_config = load_config()
client = MikroTikClient(current_config)
telegram_alert_manager = TelegramAlertManager()

# Variáveis globais de monitoramento contínuo em segundo plano (Serviço)
active_websockets: Set[WebSocket] = set()
latest_snapshot: Dict[str, Any] = {}
collector_task: Optional[asyncio.Task] = None
collector_running: bool = False
collector_stats: Dict[str, Any] = {
    "start_time": time.time(),
    "cycles_completed": 0,
    "last_cycle_time": 0.0,
    "last_error": None
}

# Rastreamento de deltas de tráfego e telemetria de hardware
prev_wan_rx = 0
prev_wan_tx = 0
last_hw_sample_time = 0.0
device_baseline_synced = False

def reset_traffic_accounting():
    """Reseta o rastreador de deltas de tráfego (usado ao alternar roteador ou zerar histórico)."""
    global prev_wan_rx, prev_wan_tx, last_hw_sample_time, device_baseline_synced
    prev_wan_rx = 0
    prev_wan_tx = 0
    last_hw_sample_time = 0.0
    device_baseline_synced = False
    logger.info("Rastreamento de deltas de tráfego reinicializado.")

def process_traffic_accounting(data: dict):
    global prev_wan_rx, prev_wan_tx, last_hw_sample_time, device_baseline_synced
    from database import record_hardware_sample

    now = time.time()

    # 1. Telemetria de Hardware (amostrada a cada 5 segundos)
    if now - last_hw_sample_time >= 4.5:
        sys_info = data.get("system", {})
        try:
            cpu_val = float(sys_info.get("cpu_load", 0))
            mem_pct = float(sys_info.get("memory_usage_pct", 0))
            free_mb = float(sys_info.get("free_memory", 0)) / (1024 * 1024)
            temp = float(sys_info.get("temperature", 42.0) or 42.0)
            volt = float(sys_info.get("voltage", 24.0) or 24.0)
            record_hardware_sample(cpu_val, mem_pct, free_mb, temp, volt)
            last_hw_sample_time = now
        except Exception as e:
            logger.debug(f"Erro ao salvar amostra de hardware: {e}")

    # 2. Sincronização inicial da linha de base de dispositivos a partir do conntrack
    devices = data.get("devices", [])
    if devices and not device_baseline_synced:
        has_real_bytes = any(d.get("total_bytes", 0) > 0 for d in devices)
        if has_real_bytes:
            sync_device_baseline(devices)
            device_baseline_synced = True
            logger.info("Linha de base de consumo individual dos dispositivos sincronizada com sucesso.")

    # 3. Contabilização de tráfego WAN e distribuição proporcional por atividade real
    traffic = data.get("traffic", {})
    curr_rx = traffic.get("total_rx_bytes", 0)
    curr_tx = traffic.get("total_tx_bytes", 0)

    if prev_wan_rx > 0 and (curr_rx >= prev_wan_rx and curr_tx >= prev_wan_tx):
        delta_rx = curr_rx - prev_wan_rx
        delta_tx = curr_tx - prev_wan_tx

        if delta_rx > 0 or delta_tx > 0:
            dev_deltas = []
            if devices:
                weights = []
                for dev in devices:
                    dev_b = dev.get("total_bytes", 0)
                    dev_r = dev.get("current_rate_rx", 0) + dev.get("current_rate_tx", 0)
                    dev_c = dev.get("active_conns", 0)
                    w = (dev_b / 1024.0) + (dev_r * 2.0) + (dev_c * 50.0)
                    weights.append(w)

                total_w = sum(weights)
                if total_w > 0:
                    for dev, w in zip(devices, weights):
                        if w <= 0:
                            part_rx = 0
                            part_tx = 0
                        else:
                            ratio = w / total_w
                            part_rx = int(delta_rx * ratio)
                            part_tx = int(delta_tx * ratio)

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

    # 4. Verificação de Alertas no Telegram (Queda de Link e Alta Temperatura)
    if current_config.telegram_enabled:
        try:
            asyncio.create_task(telegram_alert_manager.check_alerts(current_config, data))
        except Exception as e:
            logger.debug(f"Erro ao verificar alertas Telegram: {e}")

async def background_monitoring_worker():
    """
    Serviço contínuo em segundo plano que roda 24/7.
    Coleta dados do roteador, registra no banco SQLite, processa alertas e
    difunde em tempo real para os navegadores conectados.
    """
    global latest_snapshot, collector_running, collector_stats, current_config, client
    logger.info("Iniciando serviço de monitoramento contínuo em segundo plano (24/7)...")
    collector_running = True
    last_cfg_mtime = CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else 0.0

    while collector_running:
        t0 = time.time()
        try:
            # Recarrega automaticamente se o arquivo config.json foi alterado pela janela de configurações
            if CONFIG_FILE.exists():
                curr_mtime = CONFIG_FILE.stat().st_mtime
                if curr_mtime > last_cfg_mtime:
                    last_cfg_mtime = curr_mtime
                    current_config = load_config()
                    client = MikroTikClient(current_config)
                    logger.info("Configurações recarregadas automaticamente a partir do config.json.")

            if current_config.demo_mode:
                data = get_mock_snapshot()
                data["mode"] = "demo"
            else:
                try:
                    data = await client.get_full_snapshot()
                    data["mode"] = "live"
                except Exception as e:
                    logger.warning(f"Aviso de conexão MikroTik ({current_config.router_ip}): {e}. Alternando temporariamente para dados mockados.")
                    data = get_mock_snapshot()
                    data["mode"] = "fallback"
                    data["error"] = f"Não foi possível contactar {current_config.router_ip}: {str(e)}"

            # Adiciona informações dos múltiplos roteadores ao payload do dashboard
            active_dev = current_config.get_active_router()
            data["active_router_id"] = current_config.active_router_id
            data["active_router_name"] = active_dev.name
            data["routers"] = [
                {
                    "id": r.id,
                    "name": r.name,
                    "router_ip": r.router_ip,
                    "port": r.port,
                    "use_https": r.use_https,
                    "wan_interface": r.wan_interface,
                    "is_active": (r.id == current_config.active_router_id)
                }
                for r in current_config.routers
            ]

            process_traffic_accounting(data)
            latest_snapshot = data

            collector_stats["cycles_completed"] += 1
            collector_stats["last_cycle_time"] = time.time() - t0
            collector_stats["last_error"] = None

            # Difunde para painéis/dashboards que estejam abertos
            if active_websockets:
                payload = json.dumps(data)
                dead_sockets = set()
                for ws in list(active_websockets):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        dead_sockets.add(ws)
                active_websockets.difference_update(dead_sockets)

        except asyncio.CancelledError:
            logger.info("Serviço de monitoramento cancelado / desligando.")
            break
        except Exception as err:
            logger.error(f"Erro no ciclo do serviço de monitoramento: {err}")
            collector_stats["last_error"] = str(err)

        sleep_time = max(1.0, current_config.poll_interval)
        await asyncio.sleep(sleep_time)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida do serviço de segundo plano."""
    global collector_task, collector_running
    collector_running = True
    collector_task = asyncio.create_task(background_monitoring_worker())
    
    # Iniciar resolução de MACs com macvendors.com
    from mac_vendor import mac_vendor_resolver
    mac_vendor_resolver.start_worker()

    yield
    collector_running = False
    if collector_task:
        collector_task.cancel()
        try:
            await collector_task
        except asyncio.CancelledError:
            pass
    logger.info("Serviço de monitoramento encerrado.")

app = FastAPI(title="CBLhomemonitor Service", version="1.4.0", lifespan=lifespan)

# Montar arquivos estáticos
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class RouterItemUpdate(BaseModel):
    id: Optional[str] = None
    name: str = "MikroTik Principal"
    router_ip: str = "192.168.88.1"
    port: int = 80
    use_https: bool = False
    verify_ssl: bool = False
    username: str = "admin"
    password: Optional[str] = ""
    wan_interface: str = "ether1"
    poll_interval: float = 2.0

class ConfigUpdateRequest(BaseModel):
    # Suporte a múltiplos roteadores
    routers: Optional[List[RouterItemUpdate]] = None
    active_router_id: Optional[str] = None
    clear_database: Optional[bool] = False

    # Campos individuais do roteador ativo (retrocompatibilidade)
    router_ip: Optional[str] = None
    port: int = 80
    use_https: bool = False
    verify_ssl: bool = False
    username: str = "admin"
    password: str = ""
    wan_interface: str = "ether1"
    poll_interval: float = 2.0
    demo_mode: bool = False
    server_port: int = 8000

    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_temp_threshold: float = 60.0
    telegram_notify_wan_down: bool = True
    telegram_notify_temp_high: bool = True

class SwitchRouterRequest(BaseModel):
    router_id: str
    clear_database: bool = False

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
        return HTMLResponse("<h1>CBLhomemonitor - Carregando Interface...</h1>")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/service/status")
async def api_service_status():
    """Retorna o estado do serviço de monitoramento em segundo plano."""
    return {
        "status": "running" if collector_running else "stopped",
        "cycles_completed": collector_stats["cycles_completed"],
        "connected_dashboards": len(active_websockets),
        "router_ip": current_config.router_ip,
        "active_router_id": current_config.active_router_id,
        "active_router_name": current_config.get_active_router().name,
        "routers_count": len(current_config.routers),
        "demo_mode": current_config.demo_mode,
        "poll_interval": current_config.poll_interval,
        "mode": latest_snapshot.get("mode", "initializing"),
        "last_error": collector_stats["last_error"]
    }

@app.get("/api/config")
async def get_current_configuration():
    cfg = current_config.model_dump()
    cfg["password_set"] = bool(cfg.get("password"))
    cfg["password"] = "••••••••" if cfg.get("password") else ""
    
    # Mascarar senhas na lista de roteadores
    for r in cfg.get("routers", []):
        r["password_set"] = bool(r.get("password"))
        r["password"] = "••••••••" if r.get("password") else ""
        
    return cfg

@app.post("/api/config")
async def update_configuration(new_cfg: ConfigUpdateRequest):
    global current_config, client

    # Se o usuário optou por limpar o banco de dados ao salvar
    if new_cfg.clear_database:
        clear_all_history()
        reset_traffic_accounting()
        logger.info("Banco de dados zerado a pedido do usuário ao salvar novas configurações.")

    # Mapear senhas antigas para não sobrescrever com máscara ou vazio
    existing_pwds = {r.id: r.password for r in current_config.routers}

    # Atualizar ou construir a lista de roteadores
    updated_routers: List[MikroTikDevice] = []
    if new_cfg.routers is not None and len(new_cfg.routers) > 0:
        for idx, r_in in enumerate(new_cfg.routers):
            rid = r_in.id or f"router_{int(time.time() * 1000)}_{idx}"
            pwd = r_in.password
            if pwd == "••••••••" or not pwd:
                pwd = existing_pwds.get(rid, "")
                if not pwd and rid == current_config.active_router_id:
                    pwd = current_config.password

            updated_routers.append(MikroTikDevice(
                id=rid,
                name=r_in.name.strip() or f"MikroTik {idx + 1}",
                router_ip=r_in.router_ip.strip(),
                port=r_in.port or 80,
                use_https=r_in.use_https,
                verify_ssl=r_in.verify_ssl,
                username=r_in.username.strip(),
                password=pwd,
                wan_interface=r_in.wan_interface.strip() or "ether1",
                poll_interval=max(1.0, float(r_in.poll_interval or 2.0))
            ))
    else:
        # Caso clássico (formulário simples): atualiza o roteador ativo existente
        active_r = current_config.get_active_router()
        pwd_to_use = new_cfg.password
        if pwd_to_use == "••••••••" or not pwd_to_use:
            pwd_to_use = active_r.password or current_config.password

        ip_to_use = new_cfg.router_ip.strip() if new_cfg.router_ip else active_r.router_ip

        updated_active = MikroTikDevice(
            id=active_r.id,
            name=active_r.name,
            router_ip=ip_to_use,
            port=new_cfg.port,
            use_https=new_cfg.use_https,
            verify_ssl=new_cfg.verify_ssl,
            username=new_cfg.username.strip() if new_cfg.username else active_r.username,
            password=pwd_to_use,
            wan_interface=new_cfg.wan_interface.strip() if new_cfg.wan_interface else active_r.wan_interface,
            poll_interval=max(1.0, new_cfg.poll_interval)
        )
        # Substitui na lista
        replaced = False
        for r in current_config.routers:
            if r.id == active_r.id:
                updated_routers.append(updated_active)
                replaced = True
            else:
                updated_routers.append(r)
        if not replaced:
            updated_routers.append(updated_active)

    # Determinar id ativo
    active_id = new_cfg.active_router_id or current_config.active_router_id
    if not any(r.id == active_id for r in updated_routers):
        active_id = updated_routers[0].id

    # Telegram tokens
    token_to_use = new_cfg.telegram_bot_token.strip()
    if token_to_use == "••••••••" or (not token_to_use and current_config.telegram_bot_token):
        token_to_use = current_config.telegram_bot_token

    updated = RouterConfig(
        routers=updated_routers,
        active_router_id=active_id,
        demo_mode=new_cfg.demo_mode,
        server_port=new_cfg.server_port or 8000,
        telegram_enabled=new_cfg.telegram_enabled,
        telegram_bot_token=token_to_use,
        telegram_chat_id=new_cfg.telegram_chat_id.strip(),
        telegram_temp_threshold=new_cfg.telegram_temp_threshold,
        telegram_notify_wan_down=new_cfg.telegram_notify_wan_down,
        telegram_notify_temp_high=new_cfg.telegram_notify_temp_high
    )
    updated.sync_active_fields()

    save_config(updated)
    current_config = updated
    client = MikroTikClient(current_config)

    connection_test = None
    if not current_config.demo_mode:
        connection_test = await client.test_connection()

    return {
        "status": "success",
        "message": "Configurações salvas e aplicadas com sucesso!",
        "database_cleared": bool(new_cfg.clear_database),
        "active_router": current_config.get_active_router().model_dump(),
        "connection_test": connection_test,
        "demo_mode": current_config.demo_mode
    }

@app.post("/api/routers/switch")
async def switch_router_endpoint(req: SwitchRouterRequest):
    """Alterna rapidamente o MikroTik ativo que está sendo monitorado."""
    global current_config, client
    if not current_config.set_active_router(req.router_id):
        raise HTTPException(status_code=404, detail="Roteador selecionado não foi encontrado.")

    if req.clear_database:
        clear_all_history()
    reset_traffic_accounting()

    save_config(current_config)
    client = MikroTikClient(current_config)

    logger.info(f"Roteador ativo alterado para: {current_config.get_active_router().name} ({current_config.router_ip})")

    conn_test = None
    if not current_config.demo_mode:
        conn_test = await client.test_connection()

    return {
        "status": "success",
        "message": f"Monitorando agora: {current_config.get_active_router().name} ({current_config.router_ip})",
        "active_router_id": current_config.active_router_id,
        "active_router": current_config.get_active_router().model_dump(),
        "connection_test": conn_test
    }

@app.post("/api/test-connection")
async def test_connection_endpoint(test_cfg: ConfigUpdateRequest):
    pwd = test_cfg.password
    ip = test_cfg.router_ip.strip() if test_cfg.router_ip else current_config.router_ip
    if pwd == "••••••••" or not pwd:
        # Se for o mesmo IP do ativo, usa senha atual
        if ip == current_config.router_ip:
            pwd = current_config.password
        else:
            # Procura na lista de roteadores
            for r in current_config.routers:
                if r.router_ip == ip and r.password:
                    pwd = r.password
                    break

    temp_cfg = RouterConfig(
        router_ip=ip,
        port=test_cfg.port,
        use_https=test_cfg.use_https,
        verify_ssl=test_cfg.verify_ssl,
        username=test_cfg.username.strip() if test_cfg.username else "admin",
        password=pwd or ""
    )
    temp_client = MikroTikClient(temp_cfg)
    result = await temp_client.test_connection()
    return result

@app.get("/api/status")
async def get_status():
    """Retorna o snapshot mais recente coletado pelo serviço de background."""
    if latest_snapshot:
        return latest_snapshot

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
    return data

@app.get("/api/history/daily")
async def api_daily_history(days: int = 30):
    return get_daily_history(days=min(90, max(7, days)))

@app.get("/api/history/monthly")
async def api_monthly_history(months: int = 12):
    return get_monthly_history(months=min(24, max(3, months)))

@app.get("/api/history/hardware")
async def api_hardware_history(timeframe: str = "1h"):
    from database import get_hardware_history
    if timeframe not in ["1h", "6h", "24h"]:
        timeframe = "1h"
    return get_hardware_history(timeframe=timeframe)

@app.get("/api/consumption/devices")
async def api_device_consumption(period: str = "month"):
    if period not in ["today", "7days", "month"]:
        period = "month"
    return get_device_consumption_ranking(period=period)

@app.post("/api/history/clear")
async def api_clear_history():
    from database import clear_all_history
    clear_all_history()
    reset_traffic_accounting()
    return {
        "status": "success",
        "message": "Todo o histórico do banco de dados foi limpo e o monitoramento foi reinicializado com sucesso."
    }

@app.post("/api/telegram/test")
async def api_telegram_test(req: TelegramTestRequest):
    token = req.bot_token.strip() or current_config.telegram_bot_token
    chat_id = req.chat_id.strip() or current_config.telegram_chat_id
    if not token or not chat_id:
        return {"success": False, "error": "Informe o Bot Token e o Chat ID para testar."}

    test_msg = (
        "🚀 *CBLhomemonitor - Teste de Notificação!*\n\n"
        "Seu bot do Telegram foi configurado com sucesso para o monitor de rede residencial MikroTik.\n\n"
        "🔔 *Alertas Monitorados 24/7 pelo Serviço:*\n"
        f"• Queda e Restabelecimento do Link WAN\n"
        f"• Superaquecimento do Hardware (Limite: {current_config.telegram_temp_threshold}°C)\n\n"
        f"⏰ _Envio realizado em {time.strftime('%d/%m/%Y às %H:%M:%S')}_"
    )
    res = await send_telegram_message(token, chat_id, test_msg)
    return res

@app.get("/api/vendors/stats")
async def get_vendor_stats():
    from mac_vendor import mac_vendor_resolver
    return mac_vendor_resolver.get_stats()

@app.post("/api/ping")
async def ping_endpoint(req: PingRequest):
    if current_config.demo_mode:
        return mock_ping(req.address, req.count)
    try:
        res = await client.ping(req.address, req.count)
        if "error" in res:
            return mock_ping(req.address, req.count)
        return res
    except Exception:
        return mock_ping(req.address, req.count)

@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """
    O painel web conecta a este WebSocket apenas para visualizar/monitorar.
    O serviço contínuo de background faz o envio automático de cada ciclo.
    """
    await websocket.accept()
    active_websockets.add(websocket)
    logger.info(f"Painel conectado ao stream WebSocket (Total navegadores ativos: {len(active_websockets)})")
    
    try:
        # Envia imediatamente o último snapshot em cache para não deixar o painel em branco
        if latest_snapshot:
            await websocket.send_text(json.dumps(latest_snapshot))

        while True:
            # Mantém vivo ouvindo possíveis heartbeats ou aguardando disconnect
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"Desconexão de WebSocket: {e}")
    finally:
        active_websockets.discard(websocket)
        logger.info(f"Painel desconectado do stream WebSocket (Restantes: {len(active_websockets)})")
