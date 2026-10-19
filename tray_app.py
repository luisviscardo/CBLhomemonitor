"""
CBLhomemonitor ⚡ - Aplicativo de Barra de Tarefas (Windows System Tray)
Gerencia o Serviço de Monitoramento em Segundo Plano, permite Iniciar, Parar,
Configurar o MikroTik e abrir o Painel Web no navegador.
"""
import os
import sys
import time
import ctypes
import webbrowser
import threading
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

# Em modo compilado sem console (--windowed), stdout/stderr podem ser None, o que afeta o uvicorn
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import pystray
from pystray import MenuItem as item, Menu

from config import load_config, save_config, get_app_dir, get_resource_dir, RouterConfig
from autostart import is_autostart_enabled, set_autostart
from settings_gui import SettingsWindow

MUTEX_NAME = "Global\\CBLhomemonitor_SingleInstance_Mutex"

class ServerThread(threading.Thread):
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server = None
        self.is_running = False

    def run(self):
        try:
            import uvicorn
            from app import app
            config = uvicorn.Config(
                app=app,
                host=self.host,
                port=self.port,
                log_level="warning",
                access_log=False
            )
            self.server = uvicorn.Server(config)
            self.is_running = True
            self.server.run()
        except Exception as e:
            print(f"Erro no servidor uvicorn: {e}")
        finally:
            self.is_running = False

    def stop(self):
        if self.server:
            self.server.should_exit = True
        self.is_running = False

class CBLTrayApp:
    def __init__(self):
        self.config = load_config()
        self.server_thread = None
        self.icon = None
        self.settings_process = None

    def _get_icon_image(self, active: bool = True):
        """Carrega ou gera o ícone de bandeja com indicador visual de status."""
        ico_path = get_resource_dir() / "static" / "img" / "icon.png"
        if not ico_path.exists():
            ico_path = get_app_dir() / "static" / "img" / "icon.png"
        if ico_path.exists():
            try:
                base_img = Image.open(ico_path).convert("RGBA").resize((64, 64))
            except Exception:
                base_img = None
        else:
            base_img = None

        if base_img is None:
            # Fallback em memória
            base_img = Image.new("RGBA", (64, 64), (15, 23, 42, 255))
            draw = ImageDraw.Draw(base_img)
            draw.polygon([(32, 4), (60, 16), (60, 48), (32, 60), (4, 48), (4, 16)],
                         fill=(15, 23, 42, 255), outline=(0, 240, 255, 255), width=2)
            draw.polygon([(34, 14), (20, 34), (32, 34), (28, 52), (44, 28), (32, 28), (38, 14)],
                         fill=(0, 240, 255, 255))

        # Indicador de bolinha de status (Verde = Ativo, Vermelho/Cinza = Parado)
        draw = ImageDraw.Draw(base_img)
        status_color = (16, 185, 129, 255) if active else (239, 68, 68, 255)
        draw.ellipse((46, 46, 62, 62), fill=status_color, outline=(255, 255, 255, 230), width=2)
        return base_img

    def start_service(self):
        """Inicia o serviço em segundo plano."""
        if self.server_thread and self.server_thread.is_alive():
            return

        port = getattr(self.config, "server_port", 8000) or 8000
        self.server_thread = ServerThread(host=self.config.server_host, port=port)
        self.server_thread.start()

        # Atualizar ícone e menu
        if self.icon:
            self.icon.icon = self._get_icon_image(active=True)
            self.icon.title = f"CBLhomemonitor ⚡ - Serviço Ativo (Porta {port})"
            self.icon.menu = self._build_menu()
            try:
                self.icon.notify(f"Serviço em segundo plano ativo na porta {port}!", "CBLhomemonitor ⚡")
            except Exception:
                pass

    def stop_service(self):
        """Interrompe o serviço em segundo plano."""
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread = None

        if self.icon:
            self.icon.icon = self._get_icon_image(active=False)
            self.icon.title = "CBLhomemonitor ⚡ - Serviço Parado"
            self.icon.menu = self._build_menu()
            try:
                self.icon.notify("Serviço de monitoramento pausado.", "CBLhomemonitor ⚡")
            except Exception:
                pass

    def restart_service(self):
        """Reinicia o serviço com nova configuração."""
        self.stop_service()
        time.sleep(1.0)
        self.config = load_config()
        self.start_service()

    def is_service_running(self) -> bool:
        return bool(self.server_thread and self.server_thread.is_alive())

    def open_dashboard(self):
        """Abre o painel de monitoramento no navegador padrão."""
        port = getattr(self.config, "server_port", 8000) or 8000
        url = f"http://localhost:{port}"
        webbrowser.open(url)

    def open_settings(self):
        """Abre a janela de configurações nativa em processo isolado."""
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--settings"]
            else:
                cmd = [sys.executable, str(get_app_dir() / "tray_app.py"), "--settings"]

            subprocess.Popen(cmd)
        except Exception as e:
            print(f"Erro ao abrir configurações: {e}")

    def toggle_autostart(self):
        current = is_autostart_enabled()
        set_autostart(not current)
        if self.icon:
            self.icon.menu = self._build_menu()

    def exit_app(self):
        """Encerra completamente o serviço e o app de bandeja."""
        self.stop_service()
        if self.icon:
            self.icon.stop()
        sys.exit(0)

    def _build_menu(self):
        port = getattr(self.config, "server_port", 8000) or 8000
        status_label = f"🟢 Serviço: Rodando (porta {port})" if self.is_service_running() else "🔴 Serviço: Parado"

        return Menu(
            item("⚡ CBLhomemonitor v1.2", lambda: None, enabled=False),
            item(status_label, lambda: None, enabled=False),
            Menu.SEPARATOR,
            item("🌐 Abrir Painel de Monitoramento", lambda: self.open_dashboard(), default=True),
            item("▶️ Iniciar Serviço", lambda: self.start_service(), enabled=lambda item: not self.is_service_running()),
            item("⏹️ Parar Serviço", lambda: self.stop_service(), enabled=lambda item: self.is_service_running()),
            item("🔄 Reiniciar Serviço", lambda: self.restart_service()),
            Menu.SEPARATOR,
            item("⚙️ Configurações do MikroTik...", lambda: self.open_settings()),
            item("📁 Abrir Pasta do Sistema", lambda: webbrowser.open(str(get_app_dir()))),
            item("🚀 Iniciar com o Windows", lambda: self.toggle_autostart(), checked=lambda item: is_autostart_enabled()),
            Menu.SEPARATOR,
            item("❌ Sair do CBLhomemonitor", lambda: self.exit_app())
        )

    def run(self):
        # Iniciar o serviço automaticamente ao abrir o tray app
        self.start_service()

        self.icon = pystray.Icon(
            name="CBLhomemonitor",
            icon=self._get_icon_image(active=True),
            title="CBLhomemonitor ⚡ - Monitor Residencial MikroTik",
            menu=self._build_menu()
        )

        # Executa o loop de eventos da bandeja do sistema
        self.icon.run()

def main():
    # Se chamado com argumento --settings, abre apenas a janela de configurações
    if "--settings" in sys.argv:
        from settings_gui import show_settings_window
        show_settings_window()
        return

    # Verificação de Instância Única no Windows via Mutex
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_error = kernel32.GetLastError()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        # Abre o navegador caso já esteja rodando
        cfg = load_config()
        port = getattr(cfg, "server_port", 8000) or 8000
        webbrowser.open(f"http://localhost:{port}")
        return

    app = CBLTrayApp()
    try:
        app.run()
    finally:
        kernel32.CloseHandle(mutex)

if __name__ == "__main__":
    main()
