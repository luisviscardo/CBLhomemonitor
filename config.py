import json
import os
import sys
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field

def get_app_dir() -> Path:
    """Retorna o diretório base da aplicação (compatível com modo script e executável PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def get_resource_dir() -> Path:
    """Retorna o diretório de recursos empacotados (suporta PyInstaller _MEIPASS e modo script)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return get_app_dir()

CONFIG_FILE = get_app_dir() / "config.json"

class MikroTikDevice(BaseModel):
    id: str = "default"
    name: str = "MikroTik Principal"
    router_ip: str = "192.168.88.1"
    port: int = 80
    use_https: bool = False
    verify_ssl: bool = False
    username: str = "admin"
    password: str = ""
    wan_interface: str = "ether1"
    poll_interval: float = 2.0

class RouterConfig(BaseModel):
    # Lista de Roteadores MikroTik
    routers: List[MikroTikDevice] = Field(default_factory=list)
    active_router_id: str = "default"

    # MikroTik RouterOS (campos mantidos e sincronizados com o roteador ativo para retrocompatibilidade)
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

    def get_active_router(self) -> MikroTikDevice:
        """Retorna o objeto do roteador atualmente ativo na configuração."""
        if self.routers:
            for r in self.routers:
                if r.id == self.active_router_id:
                    return r
            return self.routers[0]
        return MikroTikDevice(
            id="default",
            name="MikroTik Principal",
            router_ip=self.router_ip,
            port=self.port,
            use_https=self.use_https,
            verify_ssl=self.verify_ssl,
            username=self.username,
            password=self.password,
            wan_interface=self.wan_interface,
            poll_interval=self.poll_interval
        )

    def set_active_router(self, router_id: str) -> bool:
        """Altera o roteador ativo e sincroniza as propriedades de nível superior."""
        for r in self.routers:
            if r.id == router_id:
                self.active_router_id = router_id
                self.sync_active_fields()
                return True
        return False

    def sync_active_fields(self) -> None:
        """Sincroniza os campos raiz (router_ip, etc.) com o roteador ativo."""
        active = self.get_active_router()
        self.router_ip = active.router_ip
        self.port = active.port
        self.use_https = active.use_https
        self.verify_ssl = active.verify_ssl
        self.username = active.username
        self.password = active.password
        self.wan_interface = active.wan_interface
        self.poll_interval = active.poll_interval
        self.active_router_id = active.id

def load_config() -> RouterConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg = RouterConfig(**data)
                # Migração automática: se a lista de roteadores estiver vazia, cria o primeiro baseado nos campos raiz
                if not cfg.routers:
                    dev = MikroTikDevice(
                        id="default",
                        name="MikroTik Principal",
                        router_ip=cfg.router_ip,
                        port=cfg.port,
                        use_https=cfg.use_https,
                        verify_ssl=cfg.verify_ssl,
                        username=cfg.username,
                        password=cfg.password,
                        wan_interface=cfg.wan_interface,
                        poll_interval=cfg.poll_interval
                    )
                    cfg.routers = [dev]
                    cfg.active_router_id = "default"
                cfg.sync_active_fields()
                return cfg
        except Exception as e:
            print(f"Erro ao carregar config.json: {e}")
    default_dev = MikroTikDevice(id="default", name="MikroTik Principal")
    default_config = RouterConfig(routers=[default_dev], active_router_id="default")
    default_config.sync_active_fields()
    save_config(default_config)
    return default_config

def save_config(config: RouterConfig) -> None:
    config.sync_active_fields()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)
