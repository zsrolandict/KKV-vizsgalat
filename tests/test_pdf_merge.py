import copy
import unittest
from tests import test_pdf_tao as fixtures
from app.pdf_merge import proposals, merge
from tests.test_tao_control import assessment


class MergeAPITests(unittest.TestCase):
    setUp = fixtures.PDFAPITests.setUp
    tearDown = fixtures.PDFAPITests.tearDown
    upload = fixtures.PDFAPITests.upload
    payload = fixtures.PDFAPITests.payload

    def prepare(self, module):
        first = self.upload()
        p = self.payload(first, module)
        r = self.client.post(f"/api/pdf/batches/{first['id']}/apply", json=p, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        cid = r.json()['id']
        base = ('/api/tao/cases/' if module == 'tao' else '/api/cases/') + cid
        old = self.client.get(base).json()
        batch = self.upload()
        p = self.payload(batch, module)
        p.update(target_case_id=cid, version=1)
        p['documents'][0]['name'] = 'Frissített cégnév'
        url = f"/api/pdf/batches/{batch['id']}"
        r = self.client.post(url+'/compare', json=p, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        return p, url, base, old, r.json()

    def test_selected_changes_and_old_snapshot_both_modules(self):
        for module in ('tao', 'kkv'):
            with self.subTest(module=module):
                p, url, base, old, preview = self.prepare(module)
                self.assertEqual(self.client.get(base).json()['version'], 1)
                again = self.client.post(url+'/compare', json=p, headers=self.h).json()
                self.assertEqual(preview['token'], again['token'])
                selected = [op['id'] for op in preview['operations'] if op['collection']=='companies' and op['old']]
                self.assertTrue(selected)
                p.update(token=preview['token'], selected=selected)
                r = self.client.post(url+'/merge', json=p, headers=self.h)
                self.assertEqual(r.status_code, 200, r.text)
                fresh = self.client.get(base).json()
                self.assertEqual(fresh['version'], 2)
                self.assertEqual(fresh['status'], 'draft')
                self.assertIn('Frissített cégnév', [c['name'] for c in fresh['data']['companies']])
                prior = self.client.get(base+'/versions/1').json()
                self.assertEqual(prior['data'], old['data'])
                self.assertEqual(len(self.client.get(base+'/documents').json()), 2)
                self.assertEqual(self.client.post(url+'/merge', json=p, headers=self.h).status_code, 409)

    def test_changed_payload_stale_version_and_invalid_selection(self):
        p, url, base, old, preview = self.prepare('tao')
        p.update(token=preview['token'], selected=['invalid'])
        self.assertEqual(self.client.post(url+'/merge', json=p, headers=self.h).status_code, 422)
        self.assertEqual(len(self.client.get(base+'/documents').json()), 1)
        p['selected'] = []
        p['documents'][0]['name'] += ' megváltozott'
        self.assertEqual(self.client.post(url+'/merge', json=p, headers=self.h).status_code, 409)
        p['version'] = 2
        self.assertEqual(self.client.post(url+'/compare', json=p, headers=self.h).status_code, 409)
        self.assertEqual(self.client.get(base).json()['version'], 1)

    def test_refresh_retains_approved_version(self):
        p, url, base, old, preview = self.prepare('tao')
        raw=old['data']
        raw.update(law_date=raw['as_of'],law_source='Fiktív történeti tesztforrás',scope='Részleges vizsgálat')
        self.client.put(base,json={'data':raw,'version':1},headers=self.h)
        r=self.client.post(base+'/approve',json=dict(version=2,relationships=True,rules=True,scope=True,partial=True,note='A hiányzó tényállások külön tisztázandók'),headers=self.h)
        self.assertEqual(r.status_code,200,r.text)
        p['version']=2
        preview=self.client.post(url+'/compare',json=p,headers=self.h).json()
        p.update(token=preview['token'],selected=[])
        r=self.client.post(url+'/merge',json=p,headers=self.h)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.client.get(base).json()['approved_version'],2)
        self.assertIsNotNone(self.client.get(base+'/versions/2').json()['approved_at'])
        self.assertEqual(self.client.get(base).json()['status'],'draft')

    def test_single_company_tao_refresh_and_foreign_source(self):
        p, url, base, old, preview = self.prepare('tao')
        p['documents'][0]['owners'] = []
        p['documents'][0]['officers'] = []
        r = self.client.post(url+'/compare', json=p, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        p['documents'][0]['document_id'] = 'foreign'
        self.assertEqual(self.client.post(url+'/compare', json=p, headers=self.h).status_code, 422)


class MergeTests(unittest.TestCase):
    def test_person_identity_not_inferred_and_expert_vote_survives(self):
        old = assessment(votes=[dict(id='expert',owner='p',company='a',vote_mode='expert',votes=40,reason='Eltérő szavazatok',valid_from='2024-01-01')]).model_dump(mode='json')
        source = copy.deepcopy(old)
        source['voting_facts'][0].update(id='new', vote_mode='ownership_default', votes=None, capital=80)
        preview = proposals(old, source, 'tao', 'batch', {})
        person = next(e for e in preview['entities'] if e['id']=='p')
        self.assertEqual(person['matched_id'], '')
        preview = proposals(old, source, 'tao', 'batch', {'p':'p', 'a':'a', 'b':'b', 'c':'c'})
        final = merge(old, preview, [op['id'] for op in preview['operations']], 'tao')
        self.assertEqual(next(f for f in final.voting_facts if f.id=='expert').votes, 40)
        self.assertEqual(len(final.voting_facts), 2)

    def test_missing_entity_dependency_rejected(self):
        old = assessment().model_dump(mode='json')
        source = copy.deepcopy(old)
        source['voting_facts'] = [dict(id='new',owner='p',company='a',capital=80,valid_from='2024-01-01')]
        preview = proposals(old, source, 'tao', 'batch', {'a':'a','b':'b','c':'c'})
        selected = [op['id'] for op in preview['operations'] if op['collection']=='voting_facts']
        with self.assertRaises(ValueError):merge(old, preview, selected, 'tao')

class FinancialMergeTests(unittest.TestCase):
    def test_partial_financial_update_preserves_staff_and_its_source(self):
        from tests.helpers import sample
        old=sample().model_dump(mode='json')
        source=copy.deepcopy(old)
        old['companies'][0]['registration']=source['companies'][0]['registration']='01-09-123456'
        source['financials'][0].update(employees=None,turnover='9000000',source='Új PDF · ezer HUF → HUF ×1000',employment_method='annual')
        preview=proposals(old,source,'kkv','batch',{})
        selected=[o['id'] for o in preview['operations'] if o['collection']=='financials']
        final=merge(old,preview,selected,'kkv')
        self.assertEqual(final.financials[0].employees,2)
        self.assertEqual(final.financials[0].turnover,9000000)
        self.assertIn('Ellenőrzött beszámoló',final.financials[0].source)
        self.assertIn('Új PDF',final.financials[0].source)
        self.assertIsNone(final.financials[0].accepted)

    def test_individual_import_never_keeps_missing_consolidated_amount(self):
        from tests.helpers import sample
        old=sample().model_dump(mode='json');source=copy.deepcopy(old)
        old['companies'][0]['registration']=source['companies'][0]['registration']='01-09-123456'
        old['financials'][0].update(consolidated=True,turnover='99000000')
        source['financials'][0].update(turnover=None,balance='8000000',employees=None)
        preview=proposals(old,source,'kkv','batch',{})
        final=merge(old,preview,[o['id'] for o in preview['operations'] if o['collection']=='financials'],'kkv')
        self.assertIsNone(final.financials[0].turnover)
        self.assertIsNone(final.financials[0].employees)
        self.assertFalse(final.financials[0].consolidated)
