import time
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("telegram-notifier")

async def send_telegram_message(token: str, chat_id: str, message: str) -> Dict[str, Any]:
    """Envia mensagem formatada para o Telegram via Bot API."""
    if not token or not chat_id:
        return {"success": False, "error": "Token do Bot ou Chat ID não configurados."}

    url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
    payload = {
        "chat_id": chat_id.strip(),
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return {"success": True, "message": "Mensagem enviada com sucesso ao Telegram!"}
            else:
                err_desc = data.get("description", resp.text)
                return {"success": False, "error": f"Erro Telegram ({resp.status_code}): {err_desc}"}
    except httpx.TimeoutException:
        return {"success": False, "error": "Tempo limite esgotado ao contatar os servidores do Telegram."}
    except Exception as e:
        return {"success": False, "error": f"Falha na requisição ao Telegram: {str(e)}"}

class TelegramAlertManager:
    def __init__(self):
        self.wan_is_down: bool = False
        self.temp_is_high: bool = False
        self.last_temp_alert_time: float = 0.0

    async def check_alerts(self, config, data: Dict[str, Any]):
        """Analisa os dados atuais do roteador e dispara alertas no Telegram caso haja anomalias."""
        if not getattr(config, "telegram_enabled", False):
            return
        token = getattr(config, "telegram_bot_token", "").strip()
        chat_id = getattr(config, "telegram_chat_id", "").strip()
        if not token or not chat_id:
            return

        now_str = time.strftime("%H:%M:%S")
        sys_info = data.get("system", {})
        router_name = sys_info.get("identity") or sys_info.get("board_name") or "MikroTik"

        # -------------------------------------------------------------
        # 1. VERIFICAÇÃO DO LINK WAN (INTERNET)
        # -------------------------------------------------------------
        if getattr(config, "telegram_notify_wan_down", True):
            wan_name = getattr(config, "wan_interface", "ether1")
            interfaces = data.get("interfaces", [])
            wan_iface = next((i for i in interfaces if i.get("name") == wan_name or (not wan_name and "wan" in i.get("name", "").lower())), None)

            # Link considerado UP se a interface está em execução ('running' == 'true')
            is_running = True
            if wan_iface:
                is_running = (wan_iface.get("running") == "true" or wan_iface.get("running") is True)
            elif data.get("status") == "disconnected":
                is_running = False

            # Transição: Estava UP e caiu -> Enviar alerta de queda
            if not is_running and not self.wan_is_down:
                self.wan_is_down = True
                msg = (
                    f"🚨 *ALERTA: Link de Internet MikroTik Caiu!*\n\n"
                    f"🌐 *Roteador:* `{router_name}`\n"
                    f"🔌 *Interface:* `{wan_name}`\n"
                    f"⏰ *Horário:* `{now_str}`\n"
                    f"⚠️ *Status:* Conexão indisponível / Interface inativa.\n\n"
                    f"_Verifique o modem da operadora ou o cabo de fibra ótica._"
                )
                logger.warning("Disparando alerta de queda de link WAN no Telegram")
                await send_telegram_message(token, chat_id, msg)

            # Transição: Estava DOWN e voltou -> Enviar alerta de restabelecimento
            elif is_running and self.wan_is_down:
                self.wan_is_down = False
                msg = (
                    f"✅ *RESTABELECIDO: Link de Internet MikroTik Online!*\n\n"
                    f"🌐 *Roteador:* `{router_name}`\n"
                    f"🔌 *Interface:* `{wan_name}`\n"
                    f"⏰ *Horário:* `{now_str}`\n"
                    f"🟢 *Status:* Link restabelecido e operando normalmente!"
                )
                logger.info("Disparando aviso de restabelecimento do link WAN no Telegram")
                await send_telegram_message(token, chat_id, msg)

        # -------------------------------------------------------------
        # 2. VERIFICAÇÃO DE TEMPERATURA
        # -------------------------------------------------------------
        if getattr(config, "telegram_notify_temp_high", True):
            threshold = float(getattr(config, "telegram_temp_threshold", 60.0))
            current_temp = float(sys_info.get("temperature", 0.0) or 0.0)

            if current_temp > 0:
                # Transição: Temperatura superou o limite
                if current_temp >= threshold:
                    time_since_last = time.time() - self.last_temp_alert_time
                    # Envia no primeiro disparo ou reenvia a cada 30 minutos se continuar superaquecido
                    if not self.temp_is_high or time_since_last > 1800:
                        self.temp_is_high = True
                        self.last_temp_alert_time = time.time()
                        msg = (
                            f"🔥 *ALERTA: Temperatura Elevada no MikroTik!*\n\n"
                            f"🌐 *Roteador:* `{router_name}`\n"
                            f"🌡️ *Temperatura Atual:* *{current_temp:.1f}°C*\n"
                            f"⚠️ *Limite Configurado:* `{threshold:.1f}°C`\n"
                            f"⏰ *Horário:* `{now_str}`\n\n"
                            f"_Atenção: O equipamento está muito quente. Verifique a ventilação e o ambiente onde o roteador está instalado._"
                        )
                        logger.warning(f"Disparando alerta de alta temperatura no Telegram: {current_temp}°C")
                        await send_telegram_message(token, chat_id, msg)

                # Transição: Temperatura normalizou (abaixo do limite com margem de histerese de 3°C)
                elif current_temp <= (threshold - 3.0) and self.temp_is_high:
                    self.temp_is_high = False
                    msg = (
                        f"❄️ *NORMALIZADO: Temperatura do MikroTik Normalizada!*\n\n"
                        f"🌐 *Roteador:* `{router_name}`\n"
                        f"🌡️ *Temperatura Atual:* *{current_temp:.1f}°C*\n"
                        f"⏰ *Horário:* `{now_str}`\n"
                        f"🟢 *Status:* Temperatura estabilizada dentro da faixa segura."
                    )
                    logger.info(f"Disparando aviso de temperatura normalizada no Telegram: {current_temp}°C")
                    await send_telegram_message(token, chat_id, msg)
