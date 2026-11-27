@echo off
rem A ready window for the research commands of docs\research-guide.md (python is the project's own).
title Baghdad Network Simulator - research console
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The application is not installed yet: double-click "1 - Install.cmd" first.
  pause
  exit /b 1
)
powershell -NoExit -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\Activate.ps1'; Write-Host 'Research console. Type the commands of docs\research-guide.md here, for example:' -ForegroundColor Cyan; Write-Host '  python scripts/plan_sites.py --help'"
