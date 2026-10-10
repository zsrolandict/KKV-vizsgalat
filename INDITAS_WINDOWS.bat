@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if errorlevel 1 (
        python -m venv .venv
    ) else (
        py -3 -m venv .venv
    )
    if errorlevel 1 goto python_error
)

".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto python_error

echo A szukseges csomagok ellenorzese es frissitese...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto install_error

if exist "%ProgramFiles%\LibreOffice\program\soffice.exe" set "PATH=%ProgramFiles%\LibreOffice\program;%PATH%"
if exist "%ProgramFiles(x86)%\LibreOffice\program\soffice.exe" set "PATH=%ProgramFiles(x86)%\LibreOffice\program;%PATH%"
where soffice >nul 2>nul
if errorlevel 1 echo A PDF-exporthoz LibreOffice telepitese szukseges. A Word-export hasznalhato.

echo.
echo A program cime: http://127.0.0.1:8000
echo Az ablak maradjon nyitva a hasznalat alatt. Leallitas: Ctrl+C.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 (
    echo Az inditas nem sikerult. Ha a 8000-es port foglalt, allitsd le a korabbi peldanyt.
    pause
)
exit /b

:python_error
echo Python 3.11 vagy ujabb szukseges, a python vagy py paranccsal elerhetoen.
echo Ha a meglevo .venv regi Pythonhoz tartozik, nevezd at es inditsd ujra ezt a fajlt.
pause
exit /b 1

:install_error
echo A csomagok telepitese nem sikerult. Ellenorizd az internetkapcsolatot es a fenti hibauzenetet.
pause
exit /b 1
