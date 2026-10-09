"""Interactive local Windows launcher. Keeps Poppler configuration in local data."""
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen
from .tool_paths import configured_tool, find_pdftotext, save_tool


def main():
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    print('\nKapcsolati műhely – helyi tesztverzió\n')
    tool = configured_tool('pdftotext')
    if not tool:
        print('A PDF-importhoz egyszer meg kell adni a kicsomagolt Poppler helyét.')
        print('Másolja be a Release-… vagy poppler-… mappa teljes útvonalát.')
        while not tool:
            value = input('Poppler mappa (Enter: indítás PDF-import nélkül): ').strip()
            if not value:
                break
            found = find_pdftotext(value)
            if found:
                tool = str(found.resolve())
            else:
                print('Nem található pdftotext.exe ebben a mappában. Ellenőrizze a kicsomagolás helyét.')
    if tool:
        try:
            check = subprocess.run([tool, '-v'], capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print('A PDF-kiolvasó nem indítható: ' + str(exc))
            return 1
        if check.returncode:
            print('A PDF-kiolvasó hibát jelzett. Ellenőrizze a Poppler teljes kicsomagolását.')
            return 1
        save_tool('pdftotext', tool)
        print('PDF-kiolvasó ellenőrizve; az útvonal elmentve.')
    # LibreOffice is optional. Discover the usual Windows installer location.
    if not configured_tool('soffice'):
        office = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'LibreOffice/program/soffice.exe'
        if office.is_file():
            save_tool('soffice', office)
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8000)) == 0:
            print('A 8000-es port már használatban van. A korábbi PowerShell-ablakban állítsa le az alkalmazást Ctrl+C-vel, majd indítsa újra ezt az indítót.')
            return 1
    url = 'http://127.0.0.1:8000'
    def open_when_ready():
        for _ in range(100):
            try:
                with urlopen(url + '/api/health', timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(url)
                        return
            except OSError:
                time.sleep(.2)
    threading.Thread(target=open_when_ready, daemon=True).start()
    print('A böngésző automatikusan megnyílik. Ezt az ablakot hagyja nyitva. Leállítás: Ctrl+C.\n')
    try:
        return subprocess.call([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'])
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
