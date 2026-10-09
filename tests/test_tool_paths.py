import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.tool_paths import configured_tool, find_pdftotext, save_tool


class ToolPathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'KKV_DATA_DIR':self.temp.name},clear=True);self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def test_release_directory_with_spaces_and_accents(self):
        base=Path(self.temp.name)/'OneDrive - Minta Zrt'/'Új mappa'/'Release-26.09.0-0'
        exe=base/'poppler-26.09.0'/'Library'/'bin'/'pdftotext.exe'
        exe.parent.mkdir(parents=True);exe.write_bytes(b'test')
        self.assertEqual(find_pdftotext(str(base)),exe)
        self.assertEqual(find_pdftotext('"'+str(exe)+'"'),exe)
        self.assertIsNone(find_pdftotext(exe.parent/'missing.exe'))
    def test_saved_path_survives_missing_terminal_path(self):
        exe=Path(self.temp.name)/'pdftotext.exe';exe.write_bytes(b'test')
        save_tool('pdftotext',exe)
        with patch('app.tool_paths.shutil.which',return_value=None):
            self.assertEqual(configured_tool('pdftotext'),str(exe.resolve()))
    def test_explicit_override_and_corrupt_configuration(self):
        exe=Path(self.temp.name)/'pdftotext.exe';exe.write_bytes(b'test')
        os.environ['KKV_PDFTOTEXT']=str(exe)
        self.assertEqual(configured_tool('pdftotext'),str(exe))
        os.environ['KKV_PDFTOTEXT']=str(exe)+'missing'
        self.assertIsNone(configured_tool('pdftotext'))
        del os.environ['KKV_PDFTOTEXT']
        (Path(self.temp.name)/'tool-paths.json').write_text('[]')
        with patch('app.tool_paths.shutil.which',return_value=None):self.assertIsNone(configured_tool('pdftotext'))
        save_tool('pdftotext',exe)
        self.assertEqual(configured_tool('pdftotext'),str(exe.resolve()))
