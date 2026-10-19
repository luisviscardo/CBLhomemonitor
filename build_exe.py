"""
Script de Compilação Automatizada com PyInstaller
Gera o executável standalone do CBLhomemonitor com ícone oficial,
recursos estáticos, templates e sem janela de console (noconsole).
"""
import sys
import subprocess
import shutil
from pathlib import Path
from create_icon import generate_icons

def build_executable():
    base_dir = Path(__file__).parent.resolve()
    print("[*] Iniciando compilacao do CBLhomemonitor...")

    # 1. Garantir que os icones existem
    ico_path, png_path = generate_icons()

    # 2. Configurar caminhos e parâmetros do PyInstaller
    templates_dir = base_dir / "templates"
    static_dir = base_dir / "static"

    # Separador do add-data no Windows é ';'
    sep = ";"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",  # Não abre janela preta de terminal (noconsole)
        f"--icon={ico_path}",
        f"--add-data={templates_dir}{sep}templates",
        f"--add-data={static_dir}{sep}static",
        "--name=CBLhomemonitor",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespans",
        "--hidden-import=uvicorn.lifespans.on",
        "--hidden-import=pystray._win32",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=pydantic",
        "--hidden-import=fastapi",
        "--hidden-import=httpx",
        "--hidden-import=sqlite3",
        "--hidden-import=winreg",
        str(base_dir / "tray_app.py")
    ]

    print(f"Executando comando PyInstaller...")
    result = subprocess.run(cmd, cwd=str(base_dir))

    if result.returncode == 0:
        dist_dir = base_dir / "dist" / "CBLhomemonitor"
        exe_file = dist_dir / "CBLhomemonitor.exe"
        
        # Copia config.example.json para a pasta de distribuição
        if (base_dir / "config.example.json").exists():
            shutil.copy(base_dir / "config.example.json", dist_dir / "config.example.json")
        if (base_dir / "config.json").exists():
            shutil.copy(base_dir / "config.json", dist_dir / "config.json")

        print("\n" + "=" * 60)
        print("[OK] COMPILACAO CONCLUIDA COM SUCESSO!")
        print(f"Pasta de distribuicao: {dist_dir}")
        print(f"Executavel gerado: {exe_file}")
        print("=" * 60)
        return True
    else:
        print("\n[X] Falha na compilacao com PyInstaller.")
        return False

if __name__ == "__main__":
    build_executable()
