@echo off
setlocal
cd /d "%~dp0"
if not exist "requirements.txt" (
  echo Hianyzo requirements.txt. Az inditot az alkalmazas app mappaja melle helyezze.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Python futtatokornyezet letrehozasa...
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo A Python 3.12 nem indithato. Telepitse, majd probalja ujra.
    pause
    exit /b 1
  )
)
echo Az alkalmazas fuggosegeinek ellenorzese...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo A fuggosegek telepitese nem sikerult. A fenti hibauzenet alapjan javithato.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.windows_start
pause
