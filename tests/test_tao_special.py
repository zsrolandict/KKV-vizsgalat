import unittest
from app.tao_models import TaoAssessment
from app.tao_engine import calculate


def pe(**kw):
    return dict(id='pe',principal='a',establishment='b',kind='foreign_business_domestic_pe',tax_status='yes',
                confirmed=True,reviewed_as_of='2025-12-31',reason='Adójogi telephely igazolt',evidence={'source':'Telephelyi adóregisztráció'},**kw)


def data(facts=None,votes=None):
    return TaoAssessment(title='Speciális tények',as_of='2025-12-31',companies=[
        {'id':'a','name':'Fővállalkozás'}, {'id':'b','name':'Telephely','entity_type':'permanent_establishment'},
        {'id':'c','name':'Másik cég'}, {'id':'d','name':'Másik telephely','entity_type':'permanent_establishment'}],
        establishment_facts=facts or [],voting_facts=votes or [])


def pair(d,a,b):
    return next(r for r in calculate(d)['rows'] if {r['first'],r['second']}=={a,b})


class SpecialTests(unittest.TestCase):
    def test_direct_pe_and_abc_extension(self):
        d=data([pe()],[dict(id='v',owner='a',company='c',capital=60,valid_from='2024-01-01')])
        self.assertEqual(pair(d,'a','b')['stage'],'special_signal')
        self.assertTrue(pair(d,'b','c')['signals'])
        self.assertEqual(pair(d,'b','c')['result'],'undetermined')

    def test_management_relation_is_not_abc_extension(self):
        raw=data([pe()]).model_dump(mode='json')
        raw['decisions']=[dict(first='a',second='c',as_of='2025-12-31',result='related',confirmed=True,
                              legal_ground='management',basis='Tao f)',reason='Ügyvezetés',evidence={'source':'Forrás'})]
        self.assertFalse(pair(TaoAssessment.model_validate(raw),'b','c')['signals'])
        raw['decisions'][0]['legal_ground']='abc'
        self.assertTrue(pair(TaoAssessment.model_validate(raw),'b','c')['signals'])

    def test_same_foreign_principal_establishments(self):
        f=pe();g={**pe(),'id':'pe2','establishment':'d','kind':'other_foreign_business_pe'}
        self.assertTrue(pair(data([f,g]),'b','d')['signals'])

    def test_status_date_and_conflict(self):
        for changes in [dict(tax_status='unknown'),dict(confirmed=False),dict(reviewed_as_of=None),dict(valid_to='2025-12-31')]:
            self.assertFalse(pair(data([{**pe(),**changes}]),'a','b')['signals'])
        self.assertFalse(pair(data([pe(),{**pe(),'id':'other','tax_status':'no'}]),'a','b')['signals'])

    def test_domestic_address_not_automatically_tax_establishment(self):
        raw=data([pe()]).model_dump(mode='json');raw['companies'][1]['entity_type']='company'
        with self.assertRaises(ValueError):TaoAssessment.model_validate(raw)

    def test_trustee_capacity_not_ordinary_vote(self):
        raw=data(votes=[dict(id='v',owner='a',company='c',capital=100,valid_from='2024-01-01',capacity='trustee')]).model_dump(mode='json')
        self.assertFalse(pair(TaoAssessment.model_validate(raw),'a','c')['signals'])
        self.assertTrue(pair(TaoAssessment.model_validate(raw),'a','c')['missing'])
        raw['voting_facts'][0].update(attribution_reviewed=True,reason='Joggyakorlás igazolt',evidence={'source':'Szerződés'})
        self.assertTrue(pair(TaoAssessment.model_validate(raw),'a','c')['signals'])

    def test_trust_roles_do_not_create_control(self):
        raw=data().model_dump(mode='json');raw['trust_facts']=[dict(id='t',name='Kezelt vagyon',trustees=['a'],
            settlors=['c'],holdings=['b'],confirmed=True,rights_reviewed=True,reviewed_as_of='2025-12-31',
            reason='Szerepek ellenőrizve',evidence={'source':'BVK-szerződés'})]
        result=pair(TaoAssessment.model_validate(raw),'a','c')
        self.assertFalse(result['signals']);self.assertTrue(result['trust_facts'])

    def test_family_abc_signal_extends_to_pe_without_f_extension(self):
        raw=data([pe()]).model_dump(mode='json')
        raw['persons']=[dict(id='p',name='P'),dict(id='q',name='Q')]
        raw['family_facts']=[dict(id='f',first='p',second='q',relationship='spouse',confirmed=True,
            reviewed_as_of='2025-12-31',evidence={'source':'Igazolt házastársi nyilatkozat'})]
        raw['voting_facts']=[dict(id=owner+company,owner=owner,company=company,capital=30,valid_from='2024-01-01') for owner in ['p','q'] for company in ['a','c']]
        d=TaoAssessment.model_validate(raw)
        self.assertTrue(pair(d,'a','c')['abc_signal'])
        self.assertTrue(pair(d,'b','c')['signals'])


from tests import test_pdf_tao as api_fixtures

class SpecialAPITests(unittest.TestCase):
    setUp=api_fixtures.PDFAPITests.setUp
    tearDown=api_fixtures.PDFAPITests.tearDown

    def test_new_source_reopens_bvk_attribution_and_rejects_foreign_evidence(self):
        raw=data([pe()],votes=[dict(id='v',owner='a',company='c',capital=100,capacity='trustee',
            attribution_reviewed=True,reason='Igazolt joggyakorlás',evidence={'source':'Szerződés'},valid_from='2024-01-01')]).model_dump(mode='json')
        raw['establishment_facts'][0]['evidence']['document_id']='foreign'
        r=self.client.post('/api/tao/cases',json={'data':raw},headers=self.h)
        self.assertEqual(r.status_code,422)
        raw['establishment_facts'][0]['evidence']['document_id']=None
        r=self.client.post('/api/tao/cases',json={'data':raw},headers=self.h)
        self.assertEqual(r.status_code,200,r.text);base='/api/tao/cases/'+r.json()['id']
        r=self.client.post(base+'/documents',files={'file':('uj-nyilatkozat.txt',b'New evidence','text/plain')},headers=self.h)
        self.assertEqual(r.status_code,200,r.text)
        current=self.client.get(base).json()
        self.assertFalse(current['data']['voting_facts'][0]['attribution_reviewed'])
        self.assertFalse(current['data']['establishment_facts'][0]['confirmed'])
        self.assertFalse(any(r['signals'] for r in current['calculation']['rows']))
        prior=self.client.get(base+'/versions/1').json()
        self.assertTrue(prior['data']['voting_facts'][0]['attribution_reviewed'])
