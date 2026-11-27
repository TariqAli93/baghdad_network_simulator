@echo off
rem First-time installation: double-click this file (internet needed once).
title Baghdad Network Simulator - installation
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
echo.
pause
