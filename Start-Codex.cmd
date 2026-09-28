@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The project Python environment is missing. Follow docs/governance/ENVIRONMENT.md first.
  pause
  exit /b 1
)
set "PYTHONIOENCODING=utf-8"
echo Starting the local Codex subscription preview. Keep this window open.
echo Open the Web UI address printed below. Press Ctrl+C to stop the services.
".venv\Scripts\python.exe" -m jiuwenswarm.codex_start all
if errorlevel 1 pause
