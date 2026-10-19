import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

CONFIG_FILE = Path(__file__).parent / "config.json"

class RouterConfig(BaseModel):
    router_ip: str = "192.168.88.1"
    port: int = 80
    use_https: bool = False
    verify_ssl: bool = False
    username: str = "admin"
    password: str = ""
    wan_interface: str = "ether1"
    poll_interval: float = 2.0
    demo_mode: bool = True  # Inicia com dados realistas se o roteador não estiver acessível

    # Notificações via Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_temp_threshold: float = 60.0
    telegram_notify_wan_down: bool = True
    telegram_notify_temp_high: bool = True

def load_config() -> RouterConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return RouterConfig(**data)
        except Exception as e:
            print(f"Erro ao carregar config.json: {e}")
    default_config = RouterConfig()
    save_config(default_config)
    return default_config

def save_config(config: RouterConfig) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)
