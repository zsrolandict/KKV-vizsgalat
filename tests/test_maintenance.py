import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from app import db
from app.maintenance import backup, verify, restore, restore_active, update_package


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.data=self.root/'data'
        self.env=patch.dict(os.environ,{'KKV_DATA_DIR':str(self.data)});self.env.start();db.initialize()
        with db.connection() as con:
            con.execute("INSERT INTO users VALUES('u','Név','nev','hash','admin',1,'2026-01-01')")
            con.execute("INSERT INTO sessions VALUES('token','u','csrf','2026-12-31')")
        (self.data/'tool-paths.json').write_text('{"pdftotext":"C:/Program Files/poppler/pdftotext.exe"}')
        self.archive=self.root/'backup.zip'
    def tearDown(self):self.env.stop();self.tmp.cleanup()

    def test_roundtrip_preserves_data_and_revokes_sessions(self):
        backup(self.data,self.archive)
        self.assertEqual(verify(self.archive)['format'],'kkv-backup-1')
        dest=self.root/'restored';restore(self.archive,dest)
        con=sqlite3.connect(dest/'kkv.sqlite3')
        try:
            self.assertEqual(con.execute('SELECT name FROM users').fetchone()[0],'Név')
            self.assertEqual(con.execute('SELECT count(*) FROM sessions').fetchone()[0],0)
        finally:con.close()
        self.assertEqual((dest/'tool-paths.json').read_text(),(self.data/'tool-paths.json').read_text())
        with self.assertRaises(ValueError):restore(self.archive,dest)
        with self.assertRaises(ValueError):backup(self.data,self.archive)

    def test_corruption_and_traversal_rejected_without_destination(self):
        backup(self.data,self.archive)
        corrupt=self.root/'bad.zip'
        with zipfile.ZipFile(self.archive) as src,zipfile.ZipFile(corrupt,'w') as out:
            for info in src.infolist():out.writestr(info, b'changed' if info.filename.endswith('tool-paths.json') else src.read(info))
        with self.assertRaises(ValueError):restore(corrupt,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
        with zipfile.ZipFile(corrupt,'w') as out:out.writestr('../escape','no')
        with self.assertRaises(ValueError):verify(corrupt)
        self.assertFalse((self.root/'escape').exists())

    def test_missing_source_is_not_a_successful_backup(self):
        with db.connection() as con:
            con.execute("INSERT INTO cases VALUES('c','{}',1,'draft','d','d','u',NULL,NULL)")
            con.execute("INSERT INTO documents VALUES('d','c','a.pdf','missing.pdf',1,'hash','u','d')")
        with self.assertRaises(ValueError):backup(self.data,self.archive)
        self.assertFalse(self.archive.exists())

    @patch('app.maintenance.stopped')
    def test_restore_retains_previous_data(self,_):
        backup(self.data,self.archive)
        (self.data/'later.txt').write_text('preserve')
        previous=restore_active(self.archive,self.data)
        self.assertEqual((previous/'later.txt').read_text(),'preserve')
        self.assertFalse((self.data/'later.txt').exists())

    @patch('app.maintenance.stopped')
    def test_update_preserves_venv_data_and_rollback(self,_):
        app=self.root/'app';app.mkdir();(app/'main.py').write_text('old')
        (self.root/'.venv').mkdir();(self.root/'.venv/marker').write_text('keep')
        with tempfile.TemporaryDirectory() as package:
            src=Path(package);(src/'app').mkdir();(src/'app/main.py').write_text('new')
            (src/'requirements.txt').write_text('')
            rollback=update_package(src,self.root)
        self.assertEqual((app/'main.py').read_text(),'new')
        self.assertEqual((rollback/'app/main.py').read_text(),'old')
        self.assertEqual((self.root/'.venv/marker').read_text(),'keep')
        self.assertTrue((self.data/'kkv.sqlite3').exists())
        self.assertEqual(len(list((self.root/'backups').glob('*.zip'))),1)

    @patch('app.maintenance.stopped')
    def test_zip_distribution_and_unsafe_archive(self,_):
        package=self.root/'distribution.zip'
        with zipfile.ZipFile(package,'w') as z:
            z.writestr('KKV-vizsgalat-feat-tao-matrix/', '')
            z.writestr('KKV-vizsgalat-feat-tao-matrix/app/main.py','new')
            z.writestr('KKV-vizsgalat-feat-tao-matrix/requirements.txt','')
        update_package(package,self.root)
        self.assertEqual((self.root/'app/main.py').read_text(),'new')
        with zipfile.ZipFile(package,'w') as z:z.writestr('../outside.py','bad')
        with self.assertRaises(ValueError):update_package(package,self.root)
        self.assertEqual((self.root/'app/main.py').read_text(),'new')
