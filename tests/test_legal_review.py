import unittest
from tests import test_api as api_fixtures
from tests.test_tao_control import assessment


class LegalReviewTests(unittest.TestCase):
    setUp=api_fixtures.APITests.setUp
    tearDown=api_fixtures.APITests.tearDown

    def test_kkv_missing_and_future_legal_source_block_approval(self):
        base='/api/cases/'+self.cid
        raw=self.client.get(base).json()['data']
        raw['law_source']=''
        self.client.put(base,json={'data':raw,'version':1},headers=self.headers)
        p=dict(version=2,financials=True,relationships=True,rules=True)
        self.assertEqual(self.client.post(base+'/approve',json=p,headers=self.headers).status_code,422)
        raw.update(law_source='2026-os forrás',law_date='2026-12-31')
        self.client.put(base,json={'data':raw,'version':2},headers=self.headers);p['version']=3
        r=self.client.post(base+'/approve',json=p,headers=self.headers)
        self.assertEqual(r.status_code,422);self.assertIn('későbbi',r.text)
        raw['law_applicability']='Tesztindok: az alkalmazott 2024/2025-ös rendelkezéseket külön összevetettük.'
        self.client.put(base,json={'data':raw,'version':3},headers=self.headers);p['version']=4
        self.assertEqual(self.client.post(base+'/approve',json=p,headers=self.headers).status_code,200)

    def test_tao_historical_source_requires_explanation(self):
        raw=assessment().model_dump(mode='json')
        raw.update(law_date='2026-10-01',law_source='Fiktív 2026-os tesztforrás',scope='Részleges tesztvizsgálat')
        response=self.client.post('/api/tao/cases',json={'data':raw},headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        base='/api/tao/cases/'+response.json()['id']
        p=dict(version=1,relationships=True,rules=True,scope=True,partial=True,note='Még nem eldöntött párok')
        r=self.client.post(base+'/approve',json=p,headers=self.headers)
        self.assertEqual(r.status_code,422);self.assertIn('későbbi',r.text)
        raw['law_applicability']='A vizsgált rendelkezés korábbi szövegének összevetése – fiktív tesztindok.'
        self.client.put(base,json={'data':raw,'version':1},headers=self.headers);p['version']=2
        self.assertEqual(self.client.post(base+'/approve',json=p,headers=self.headers).status_code,200)
