"""
Gerenciamento de Inicialização Automática com o Windows (Startup / Run)
Utiliza o Registro do Windows (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
Compatível com modo script Python e executável empacotado (.exe).
"""
import sys
import winreg
from pathlib import Path
from config import get_app_dir

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "CBLhomemonitor"

def is_autostart_enabled() -> bool:
    """Verifica se o aplicativo está registrado para iniciar com o Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception:
        return False

def set_autostart(enable: bool) -> bool:
    """Ativa ou desativa a inicialização automática com o Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                if getattr(sys, "frozen", False):
                    # Executável compilado
                    cmd = f'"{sys.executable}"'
                else:
                    # Modo script
                    python_exe = sys.executable
                    # Se estiver em pythonw.exe, melhor ainda
                    tray_script = get_app_dir() / "tray_app.py"
                    cmd = f'"{python_exe}" "{tray_script}"'

                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                return True
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
                return True
    except Exception as e:
        print(f"Erro ao atualizar registro de autostart: {e}")
        return False
