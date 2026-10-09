"""Persistent paths for local PDF tools; a terminal PATH change is not required."""
import json
import os
import shutil
from pathlib import Path
from . import db


def configured_tool(name):
    override = os.environ.get('KKV_' + name.upper(), '').strip().strip('"')
    if override:
        return override if Path(override).is_file() else None
    config = db.data_dir() / 'tool-paths.json'
    if config.exists():
        try:
            value = json.loads(config.read_text(encoding='utf-8')).get(name)
            if value and Path(value).is_file():
                return str(Path(value))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return shutil.which(name)


def find_pdftotext(folder):
    folder = Path(str(folder).strip().strip('"').strip("'"))
    if folder.is_file():
        return folder if folder.name.lower() in ('pdftotext.exe', 'pdftotext') else None
    # Known ZIP layouts only, without scanning personal folders or the whole disk.
    for pattern in ('pdftotext.exe', 'Library/bin/pdftotext.exe', 'bin/pdftotext.exe',
                    '*/Library/bin/pdftotext.exe', '*/bin/pdftotext.exe'):
        result = next((p for p in folder.glob(pattern) if p.is_file()), None)
        if result:
            return result
    return None


def save_tool(name, path):
    target = db.data_dir() / 'tool-paths.json'
    try:
        settings = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    except (OSError, ValueError):
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    settings[name] = str(Path(path).resolve())
    pending = target.with_suffix('.tmp')
    pending.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(pending, target)
