@echo off
chcp 65001 >nul
title CBLhomemonitor - Serviço de Monitoramento
cd /d "%~dp0"
echo ===================================================================
echo     ⚡ CBLhomemonitor - Monitor Residencial MikroTik
echo ===================================================================
echo.
echo Iniciando o serviço com ícone na barra de tarefas (System Tray)...
echo.
start "" pythonw tray_app.py
echo [OK] O CBLhomemonitor está ativo na bandeja do sistema ao lado do relógio.
echo Clique com o botão direito no ícone para gerenciar ou configurar.
echo.
timeout /t 3 >nul
exit /b 0
