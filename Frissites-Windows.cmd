@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Elobb inditsa el az Inditas-Windows.cmd fajlt.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.maintenance update
if errorlevel 1 (
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
pause
