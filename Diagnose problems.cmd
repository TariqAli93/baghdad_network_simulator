@echo off
rem Check this computer and the installation (PASS / WARN / FAIL). Changes nothing except a saved report.
title Baghdad Network Simulator - diagnostics
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0doctor.ps1" -Save
echo.
pause
