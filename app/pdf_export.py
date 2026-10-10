"""Word-to-PDF conversion isolated from OneDrive and long Windows application paths."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from .tool_paths import configured_tool


class PDFExportError(RuntimeError):
    pass


def converter():
    tool = configured_tool('soffice')
    if not tool:
        for variable in ('PROGRAMFILES', 'PROGRAMW6432', 'PROGRAMFILES(X86)'):
            base = os.environ.get(variable)
            if base:
                candidate = Path(base)/'LibreOffice/program/soffice.exe'
                if candidate.is_file():
                    tool = str(candidate)
                    break
    if not tool:
        return None
    path = Path(tool)
    # Windows .com waits for conversion and returns console diagnostics.
    console = path.with_suffix('.com')
    return str(console) if path.suffix.lower() == '.exe' and console.is_file() else str(path)


def status():
    return {'export_available': bool(converter()), 'import_available': bool(configured_tool('pdftotext')),
            'export_message': 'PDF-exporthoz LibreOffice szükséges. A Poppler / pdftotext a PDF-beolvasást végzi.',
            'install_url': 'https://www.libreoffice.org/download/download-libreoffice/'}


def convert(docpath, target):
    tool = converter()
    if not tool:
        raise PDFExportError('A PDF-exporthoz szükséges LibreOffice nem található. Telepítsd a LibreOffice-t '
                             '(www.libreoffice.org), majd indítsd újra a programot. A Poppler csak a PDF-beolvasáshoz kell; a Word-export addig is használható.')
    try:
        # Short, local paths also avoid OneDrive synchronization/locking during conversion.
        with tempfile.TemporaryDirectory(prefix='kkv-pdf-') as folder:
            work = Path(folder)
            shutil.copyfile(docpath, work/'report.docx')
            result = subprocess.run([tool, '-env:UserInstallation='+(work/'profile').as_uri(),
                '--headless', '--convert-to', 'pdf:writer_pdf_Export', '--outdir', str(work), str(work/'report.docx')],
                check=False, timeout=90, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pdf = work/'report.pdf'
            if result.returncode or not pdf.is_file() or pdf.read_bytes()[:5] != b'%PDF-':
                raise PDFExportError('A LibreOffice elindult, de nem készített érvényes PDF-et. '
                    'Zárd be a LibreOffice ablakait, indítsd újra a programot, majd próbáld újra a PDF-exportot. A Word-export használható.')
            # Move through a temporary file on the target filesystem, then publish atomically.
            with tempfile.NamedTemporaryFile(dir=Path(target).parent, delete=False) as stream:
                stream.write(pdf.read_bytes()); pending = Path(stream.name)
            try: os.replace(pending, target)
            finally: pending.unlink(missing_ok=True)
    except PDFExportError:
        raise
    except subprocess.TimeoutExpired:
        raise PDFExportError('A LibreOffice PDF-konverziója 90 másodpercen belül nem fejeződött be. '
                             'Zárd be a LibreOffice ablakait és próbáld újra; a Word-export használható.') from None
    except OSError:
        raise PDFExportError('A PDF-konverter vagy az ideiglenes munkamappa nem érhető el. '
                             'Ellenőrizd a LibreOffice telepítését és a helyi ideiglenes mappa írási jogosultságát. A Word-export használható.') from None
