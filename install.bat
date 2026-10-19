@echo off
title CBLhomemonitor - Instalador
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if %errorlevel% neq 0 pause
exit /b %errorlevel%
