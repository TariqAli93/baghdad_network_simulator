@echo off
rem Start the application: double-click this file. Keep the window open; close it to stop.
title Baghdad Network Simulator
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
if errorlevel 1 pause
