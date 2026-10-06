from io import BytesIO
import unittest
import openpyxl
from app.importers import import_excel,template_bytes
from app.models import Assessment
from app.reports import hu


class ImportTests(unittest.TestCase):
    def test_template_roundtrip_and_precision(self):
        wb=openpyxl.load_workbook(BytesIO(template_bytes()))
        wb['Vállalkozások'].append(['a','Teszt Kft.','01-09-123456','HU','Szolgáltatás'])
        wb['Személyek'].append(['p','Teszt Személy'])
        wb['Kapcsolatok'].append(['p','a',100,100,'Cégirat'])
        for year in [2024,2025]:
            wb['Pénzügyi adatok'].append(['a',year,9.5,1234567.5,1000000,f'{year+1}-05-31',f'{year}-12-31','Beszámoló'])
            wb['Árfolyamok'].append([year,f'{year}-12-31',f'{year}-12-31',400,'MNB'])
        out=BytesIO();wb.save(out)
        data=import_excel(out.getvalue(),'teszt.xlsx')
        self.assertEqual(data.years,[2024,2025])
        self.assertEqual(str(data.financials[-1].turnover),'1234567.5')
        self.assertEqual(data.ownerships[0].votes,100)
        self.assertFalse(data.rates[0].confirmed)

    def test_invalid_structure_is_rejected(self):
        wb=openpyxl.Workbook();out=BytesIO();wb.save(out)
        with self.assertRaises(ValueError):import_excel(out.getvalue(),'other.xlsx')

    def test_hungarian_document_number_format(self):
        self.assertEqual(hu('140.5'),'140,5')
        self.assertEqual(hu('3273330.5'),'3\u00a0273\u00a0330,5')
        self.assertEqual(hu('0'),'0')


if __name__=='__main__':unittest.main()
