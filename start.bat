@echo off
title CBLhomemonitor - Monitor de Rede Residencial
cd /d "%~dp0"
echo ===================================================================
echo     CBLHOMEMONITOR - MONITOR DE REDE RESIDENCIAL
echo ===================================================================
echo.
echo Abrindo em http://localhost:8000
echo Pressione Ctrl+C no terminal para encerrar o servidor.
echo.
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause
