@echo off
title JARVIS Server Launcher
echo ===================================================
echo           Starting JARVIS AI Backend Server        
echo ===================================================
echo.
echo Binding server to 0.0.0.0:8080 for LAN and Android Mobile Access...
echo.
echo PC Web Dashboard: http://localhost:8080
echo Android App: Connect to your PC's IP Address on port 8080
echo.
cd /d %~dp0
".venv\Scripts\python.exe" -m ultron --web --lan --port 8080
pause
