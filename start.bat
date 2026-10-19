@echo off
title CBLhomemonitor - Servico de Monitoramento
cd /d "%~dp0"
echo ===================================================================
echo     CBLhomemonitor - Monitor Residencial MikroTik
echo ===================================================================
echo.
echo Iniciando o servico na barra de tarefas (System Tray)...
echo.
if exist "%~dp0CBLhomemonitor.exe" (
    start "" "%~dp0CBLhomemonitor.exe"
) else if exist "%~dp0dist\CBLhomemonitor\CBLhomemonitor.exe" (
    start "" "%~dp0dist\CBLhomemonitor\CBLhomemonitor.exe"
) else (
    start "" pythonw "%~dp0tray_app.py"
)
echo [OK] O CBLhomemonitor esta ativo na bandeja do sistema ao lado do relogio.
echo Clique com o botao direito no icone para gerenciar ou configurar.
echo.
ping -n 3 127.0.0.1 >nul
exit /b 0
