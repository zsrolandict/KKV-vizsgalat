"""Portable, verifiable local backups and reversible package updates."""
from contextlib import closing
import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

MAX_BYTES = 4 * 1024**3
MAX_FILES = 50000
PACKAGE_ITEMS = ('app', 'requirements.txt', 'README.md', 'Inditas-Windows.cmd',
                 'Mentes-Windows.cmd', 'Visszaallitas-Windows.cmd', 'Frissites-Windows.cmd', 'docs')


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024*1024), b''):h.update(part)
    return h.hexdigest()


def checked_name(name):
    p = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or p.is_absolute() or any(x in ('..', '.') for x in name.split('/')):
        raise ValueError('Nem biztonságos archív útvonal.')
    return p


def stopped():
    with socket.socket() as sock:
        sock.settimeout(.3)
        if sock.connect_ex(('127.0.0.1', 8000)) == 0:
            raise ValueError('Előbb állítsa le az alkalmazást az indítóablakban Ctrl+C-vel. A 8000-es port még használatban van.')


def check_database(folder):
    database = folder/'kkv.sqlite3'
    if not database.is_file():raise ValueError('Hiányzik az adatbázis a mentésből.')
    with closing(sqlite3.connect(database)) as con:
        if con.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Sérült SQLite-adatbázis.')
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'users','cases','versions'}.issubset(tables):raise ValueError('Ez nem KKV-adatbázis.')
        if con.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Hibás adatbázis-hivatkozás.')
        for table, prefix in [('documents',Path('uploads')),('tao_documents',Path('uploads/tao'))]:
            if table not in tables:continue
            for filename, checksum in con.execute(f'SELECT stored_name,sha256 FROM {table}'):
                checked_name(filename)
                path = folder/prefix/filename
                if not path.is_file() or sha(path)!=checksum:raise ValueError('Hiányzó vagy sérült forrásirat: '+filename)
        if 'pdf_batches' in tables:
            for bid, raw in con.execute('SELECT id,files FROM pdf_batches'):
                checked_name(bid)
                for f in json.loads(raw):
                    checked_name(f['id'])
                    path = folder/'pdf-batches'/bid/(f['id']+'.pdf')
                    if not path.is_file() or sha(path)!=f['sha256']:raise ValueError('Hiányzó vagy sérült importforrás.')


def backup(data, output):
    data, output = Path(data).resolve(), Path(output).resolve()
    if data == output or data in output.parents:raise ValueError('A mentés az adatkönyvtáron kívül legyen.')
    if output.exists():raise ValueError('A célfájl már létezik; válasszon új nevet.')
    if not (data/'kkv.sqlite3').is_file():raise ValueError('Nem található menthető adatbázis.')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kkv-backup-') as tmp:
        stage=Path(tmp)
        # Serialize application writes while taking a SQLite snapshot and copying its sources.
        lock=sqlite3.connect(data/'kkv.sqlite3',timeout=15)
        try:
            lock.execute('BEGIN IMMEDIATE')
            with closing(sqlite3.connect(data/'kkv.sqlite3')) as source, closing(sqlite3.connect(stage/'kkv.sqlite3')) as target:
                source.backup(target)
            for path in data.rglob('*'):
                if path.is_symlink():raise ValueError('Az adatkönyvtár szimbolikus linket tartalmaz.')
                if not path.is_file() or path.name in ('kkv.sqlite3','kkv.sqlite3-wal','kkv.sqlite3-shm','kkv.sqlite3-journal'):continue
                dest=stage/path.relative_to(data);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        finally:
            lock.rollback();lock.close()
        check_database(stage)
        files={p.relative_to(stage).as_posix():{'size':p.stat().st_size,'sha256':sha(p)} for p in stage.rglob('*') if p.is_file()}
        manifest={'format':'kkv-backup-1','created':datetime.now(timezone.utc).isoformat(),'files':files}
        partial=output.with_name(output.name+'.partial-'+stamp())
        try:
            with zipfile.ZipFile(partial,'x',compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
                for name in files:archive.write(stage/name,'data/'+name)
            verify(partial)
            partial.rename(output)
        finally:partial.unlink(missing_ok=True)
    return output


def unpack_backup(archive, target):
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(infos)>MAX_FILES or len(names)!=len(set(names)) or sum(i.file_size for i in infos)>MAX_BYTES:
            raise ValueError('Túl nagy vagy ismételt bejegyzéseket tartalmazó mentés.')
        for info in infos:
            checked_name(info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:raise ValueError('Szimbolikus link az archívumban.')
        if 'manifest.json' not in names or z.getinfo('manifest.json').file_size>10*1024**2:raise ValueError('Hiányzó vagy túl nagy jegyzék.')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('format')!='kkv-backup-1':raise ValueError('Ismeretlen mentésformátum.')
        files=manifest['files']
        if set(names)!={'manifest.json',*('data/'+n for n in files)}:raise ValueError('Eltér az archívum és a fájljegyzék.')
        for name, details in files.items():
            checked_name(name)
            dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
            with z.open('data/'+name) as src, dest.open('xb') as out:shutil.copyfileobj(src,out)
            if dest.stat().st_size!=details['size'] or sha(dest)!=details['sha256']:raise ValueError('Sérült mentett fájl: '+name)
        check_database(target)
        return manifest


def verify(archive):
    with tempfile.TemporaryDirectory(prefix='kkv-verify-') as tmp:
        return unpack_backup(archive,Path(tmp))


def restore(archive, destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('A visszaállítás célja még nem létező könyvtár legyen.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.kkv-restore-',dir=destination.parent) as tmp:
        stage=Path(tmp)/'data';stage.mkdir()
        unpack_backup(archive,stage)
        # Old browser sessions should not regain access after a restore.
        with closing(sqlite3.connect(stage/'kkv.sqlite3')) as con, con:con.execute('DELETE FROM sessions')
        stage.rename(destination)
    return destination


def restore_active(archive, data):
    stopped()
    data=Path(data).resolve()
    fresh=data.with_name(data.name+'-restored-'+stamp())
    restore(archive,fresh)
    previous=data.with_name(data.name+'-before-restore-'+stamp())
    try:
        if data.exists():data.rename(previous)
        fresh.rename(data)
    except Exception:
        if previous.exists() and not data.exists():previous.rename(data)
        raise
    return previous if previous.exists() else None


def update_package(source, root):
    """Replace only distribution files. Keep data, venv and a rollback copy intact."""
    stopped()
    root,source=Path(root).resolve(),Path(source).resolve()
    with tempfile.TemporaryDirectory(prefix='.kkv-update-',dir=root.parent) as tmp:
        stage=Path(tmp)
        if source.is_file():
            with zipfile.ZipFile(source) as z:
                infos=z.infolist()
                if len(infos)>MAX_FILES or sum(i.file_size for i in infos)>MAX_BYTES:raise ValueError('Túl nagy programcsomag.')
                names=set()
                for info in infos:
                    checked_name(info.filename.rstrip('/'))
                    if info.filename in names or (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Érvénytelen programcsomag.')
                    names.add(info.filename)
                z.extractall(stage)
            candidates=[p.parent for p in stage.rglob('requirements.txt') if (p.parent/'app/main.py').is_file()]
            if len(candidates)!=1:raise ValueError('Nem azonosítható egyértelműen a program a ZIP-ben.')
            package=candidates[0]
        else:package=source
        if not (package/'app/main.py').is_file() or not (package/'requirements.txt').is_file():raise ValueError('Hiányos programcsomag.')
        if package==root or root in package.parents or package in root.parents:raise ValueError('A programcsomag az alkalmazás könyvtárán kívül legyen.')
        prepared=stage/'prepared';prepared.mkdir()
        for name in PACKAGE_ITEMS:
            src=package/name
            if not src.exists():continue
            if src.is_symlink() or src.is_dir() and any(p.is_symlink() for p in src.rglob('*')):raise ValueError('Szimbolikus link a programcsomagban.')
            if src.is_dir():shutil.copytree(src,prepared/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            else:shutil.copy2(src,prepared/name)
        data=Path(os.environ.get('KKV_DATA_DIR',root/'data')).resolve()
        if (data/'kkv.sqlite3').exists():backup(data,root/'backups'/('frissites-elott-'+stamp()+'.zip'))
        rollback=root/'backups'/('program-'+stamp());rollback.mkdir(parents=True)
        installed=[];saved=[]
        try:
            for name in PACKAGE_ITEMS:
                if not (prepared/name).exists():continue
                if (root/name).exists():(root/name).rename(rollback/name);saved.append(name)
                (prepared/name).rename(root/name);installed.append(name)
        except Exception:
            for name in reversed(installed):
                p=root/name
                if p.is_dir():shutil.rmtree(p)
                else:p.unlink()
            for name in saved:(rollback/name).rename(root/name)
            raise
        return rollback


def main():
    parser=argparse.ArgumentParser(description='KKV/Tao helyi karbantartás')
    parser.add_argument('action',choices=['backup','verify','restore','update'])
    parser.add_argument('path',nargs='?')
    parser.add_argument('--data',default=os.environ.get('KKV_DATA_DIR',str(Path(__file__).resolve().parent.parent/'data')))
    parser.add_argument('--destination')
    args=parser.parse_args();root=Path(__file__).resolve().parent.parent
    try:
        if args.action=='backup':
            output=Path(args.path) if args.path else root/'backups'/('kkv-tao-'+stamp()+'.zip')
            print('Ellenőrzött mentés:',backup(args.data,output))
        else:
            path=args.path or input('A ZIP-fájl teljes elérési útja: ').strip().strip('"')
            if args.action=='verify':verify(path);print('A mentés épségellenőrzése sikeres.')
            elif args.action=='restore':
                if args.destination:print('Visszaállított könyvtár:',restore(path,args.destination))
                else:print('Visszaállítva. A korábbi adatok megmaradtak itt:',restore_active(path,args.data))
            else:print('Frissítés kész. A korábbi program itt maradt:',update_package(path,root))
    except (ValueError,OSError,sqlite3.Error,zipfile.BadZipFile,KeyError,TypeError) as exc:
        parser.exit(1,'Nem fejeződött be: '+str(exc)+'\n')


if __name__=='__main__':main()
