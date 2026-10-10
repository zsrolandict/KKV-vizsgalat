import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.pdf_export import convert, converter, PDFExportError
from app.pdf_import import extract


class PDFExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)/'OneDrive - Új mappa';self.base.mkdir()
        self.doc=self.base/'Hosszú nevű állásfoglalás.docx';self.doc.write_bytes(b'test docx')
        self.pdf=self.base/'állásfoglalás.pdf'

    def test_conversion_uses_short_local_paths_and_checks_output(self):
        def run(args,**kw):
            source=Path(args[-1]);self.assertEqual(source.name,'report.docx')
            self.assertNotEqual(source.parent,self.base);self.assertEqual(source.read_bytes(),b'test docx')
            self.assertTrue(any(a.startswith('-env:UserInstallation=file:') for a in args))
            (source.parent/'report.pdf').write_bytes(b'%PDF-1.7\nfixture')
            return subprocess.CompletedProcess(args,0,b'',b'')
        with patch('app.pdf_export.converter',return_value='soffice'),patch('app.pdf_export.subprocess.run',side_effect=run):convert(self.doc,self.pdf)
        self.assertEqual(self.pdf.read_bytes(),b'%PDF-1.7\nfixture')

    def test_missing_converter_timeout_and_missing_pdf_are_actionable(self):
        with patch('app.pdf_export.converter',return_value=None):
            with self.assertRaisesRegex(PDFExportError,'LibreOffice.*nem található'):convert(self.doc,self.pdf)
        for result,message in [(subprocess.TimeoutExpired('soffice',90),'90 másodpercen'),
                                (subprocess.CompletedProcess([],0,b'',b''),'nem készített érvényes PDF')]:
            with patch('app.pdf_export.converter',return_value='soffice'),patch('app.pdf_export.subprocess.run',side_effect=result if isinstance(result,Exception) else None,return_value=result):
                with self.assertRaisesRegex(PDFExportError,message):convert(self.doc,self.pdf)
        self.assertFalse(self.pdf.exists())

    def test_windows_installer_location_and_console_binary(self):
        program=self.base/'LibreOffice/program';program.mkdir(parents=True)
        (program/'soffice.exe').touch();(program/'soffice.com').touch()
        with patch.dict(os.environ,{'PROGRAMFILES':str(self.base)},clear=True),patch('app.pdf_export.configured_tool',return_value=None):
            self.assertEqual(converter(),str(program/'soffice.com'))

    def test_poppler_dll_failure_is_not_reported_as_a_bad_pdf(self):
        self.pdf.write_bytes(b'%PDF-1.7\nfixture')
        with patch('app.pdf_import.configured_tool',return_value='pdftotext'),patch('app.pdf_import.subprocess.run',return_value=subprocess.CompletedProcess([],0xc0000135,b'',b'')):
            with self.assertRaisesRegex(RuntimeError,'DLL'):extract(self.pdf,'teszt.pdf')
