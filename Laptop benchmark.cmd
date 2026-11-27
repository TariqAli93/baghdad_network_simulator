@echo off
rem Target-laptop acceptance measurements (docs\laptop-acceptance.md). Run on AC power; takes a while.
title Baghdad Network Simulator - laptop benchmark
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0benchmark.ps1"
echo.
pause
