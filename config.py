import json
import os
import sys
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

def get_app_dir() -> Path:
    """Retorna o diretório base da aplicação (compatível com modo script e executável PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

CONFIG_FILE = get_app_dir() / "config.json"

class RouterConfig(BaseModel):
    # MikroTik RouterOS
    router_ip: str = "192.168.88.1"
    port: int = 80
    use_https: bool = False
    verify_ssl: bool = False
    username: str = "admin"
    password: str = ""
    wan_interface: str = "ether1"
    poll_interval: float = 2.0
    demo_mode: bool = False

    # Servidor Web & Painel
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    autostart: bool = False

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
