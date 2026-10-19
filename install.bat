@echo off
chcp 65001 >nul
title CBLhomemonitor - Instalador e Inicializador Rápido

echo ========================================================
echo        ⚡ CBLhomemonitor - Instalação do Sistema
echo ========================================================
echo.

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

:: 1. Verificar se Python está instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Python não foi encontrado no seu computador.
    echo Baixando ou instalando Python automaticamente via winget...
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [X] Não foi possível instalar o Python automaticamente.
        echo Por favor, instale o Python em https://www.python.org/downloads/ marcando "Add python.exe to PATH".
        pause
        exit /b 1
    )
)

echo [1/4] Instalando e atualizando bibliotecas necessárias...
python -m pip install -r requirements.txt --quiet --no-warn-script-location

echo [2/4] Gerando ícones e recursos visuais...
python create_icon.py >nul 2>nul

echo [3/4] Criando atalhos na Área de Trabalho e Menu Iniciar...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desk = [System.Environment]::GetFolderPath('Desktop'); " ^
    "$programs = [System.Environment]::GetFolderPath('Programs'); " ^
    "$pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source; " ^
    "if (-not $pyw) { $pyw = (Get-Command python).Source }; " ^
    "$exe = Join-Path '%APP_DIR%' 'dist\CBLhomemonitor\CBLhomemonitor.exe'; " ^
    "$ico = Join-Path '%APP_DIR%' 'static\img\icon.ico'; " ^
    "$target = if (Test-Path $exe) { $exe } else { $pyw }; " ^
    "$args = if (Test-Path $exe) { '' } else { '\"' + (Join-Path '%APP_DIR%' 'tray_app.py') + '\"' }; " ^
    "$s1 = $ws.CreateShortcut((Join-Path $desk 'CBLhomemonitor.lnk')); " ^
    "$s1.TargetPath = $target; " ^
    "$s1.Arguments = $args; " ^
    "$s1.WorkingDirectory = '%APP_DIR%'; " ^
    "$s1.IconLocation = $ico; " ^
    "$s1.Description = 'CBLhomemonitor - Monitor de Rede Residencial MikroTik'; " ^
    "$s1.Save(); " ^
    "$s2 = $ws.CreateShortcut((Join-Path $programs 'CBLhomemonitor.lnk')); " ^
    "$s2.TargetPath = $target; " ^
    "$s2.Arguments = $args; " ^
    "$s2.WorkingDirectory = '%APP_DIR%'; " ^
    "$s2.IconLocation = $ico; " ^
    "$s2.Description = 'CBLhomemonitor - Monitor de Rede Residencial MikroTik'; " ^
    "$s2.Save();"

echo [4/4] Iniciando o Serviço do CBLhomemonitor na Barra de Tarefas...
start "" pythonw tray_app.py

echo.
echo ========================================================
echo   ✅ CBLhomemonitor Instalado e Iniciado com Sucesso!
echo ========================================================
echo - O serviço está rodando em segundo plano.
echo - Um ícone com raio neon foi adicionado perto do relógio do Windows (Bandeja do Sistema).
echo - Use o ícone para Iniciar, Parar ou Configurar seu MikroTik.
echo.
timeout /t 3 >nul
exit /b 0
