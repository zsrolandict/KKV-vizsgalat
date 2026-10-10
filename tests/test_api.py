import json
import os
import secrets
import tempfile
import unittest
from xml.sax.saxutils import escape
from io import BytesIO
from unittest.mock import patch
from docx import Document
from fastapi.testclient import TestClient
from app import db
from app.main import app
from .helpers import sample


class APITests(unittest.TestCase):
    def test_existing_draft_receives_guidance_without_changing_saved_snapshot(self):
        data=sample().model_dump(mode='json');data['rates'][0]['confirmed']=False
        self.client.put('/api/cases/'+self.cid,json={'data':data,'version':1},headers=self.headers)
        with db.connection() as con:
            snap=con.execute('SELECT calculation FROM versions WHERE case_id=? AND version=2',(self.cid,)).fetchone()
            old=json.loads(snap['calculation'])
            for b in old['blockers']:
                for key in ['title','why','action','destination','target']:b.pop(key,None)
            con.execute('UPDATE versions SET calculation=? WHERE case_id=? AND version=2',(json.dumps(old),self.cid))
        current=self.client.get('/api/cases/'+self.cid).json()
        self.assertEqual(current['version'],2)
        check=next(b for b in current['calculation']['blockers'] if b['code']=='rate_unconfirmed')
        self.assertEqual(check['destination'],'rate')
        self.assertIn('pipáld',check['action'])
        historical=self.client.get(f'/api/cases/{self.cid}/versions/2').json()
        self.assertNotIn('action',historical['calculation']['blockers'][0])

    def test_network_layout_is_versioned_and_does_not_change_calculation(self):
        original=self.client.get('/api/cases/'+self.cid).json()
        data=original['data'];data['graph_positions']={'a':{'x':320,'y':220}}
        saved=self.client.put('/api/cases/'+self.cid,json={'data':data,'version':1},headers=self.headers)
        self.assertEqual(saved.status_code,200,saved.text)
        current=self.client.get('/api/cases/'+self.cid).json()
        self.assertEqual(current['data']['graph_positions']['a'],{'x':320,'y':220})
        self.assertEqual(current['calculation']['years'],original['calculation']['years'])
        previous=self.client.get(f'/api/cases/{self.cid}/versions/1').json()
        self.assertFalse(previous['data'].get('graph_positions'))

    def test_network_layout_rejects_unknown_nodes_and_invalid_coordinates(self):
        for positions in [{'unknown':{'x':200,'y':200}},{'a':{'x':-1,'y':200}},{'a':{'x':200,'y':6000}}]:
            with self.subTest(positions=positions):
                data=sample().model_dump(mode='json');data['graph_positions']=positions
                result=self.client.put('/api/cases/'+self.cid,json={'data':data,'version':1},headers=self.headers)
                self.assertEqual(result.status_code,422)
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['version'],1)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'KKV_DATA_DIR':self.tmp.name});self.env.start();db.initialize()
        self.client=TestClient(app);self.password=secrets.token_urlsafe(24)
        r=self.client.post('/api/auth/setup',json={'name':'Teszt Szakértő','username':'expert','password':self.password})
        self.assertEqual(r.status_code,200);self.csrf=r.json()['csrf'];self.headers={'X-CSRF-Token':self.csrf}
        r=self.client.post('/api/cases',json={'data':sample().model_dump(mode='json')},headers=self.headers)
        self.assertEqual(r.status_code,200,r.text);self.cid=r.json()['id']

    def tearDown(self):self.client.close();self.env.stop();self.tmp.cleanup()

    def test_setup_is_single_use(self):
        r=self.client.post('/api/auth/setup',json={'name':'Other','username':'other','password':self.password})
        self.assertEqual(r.status_code,409)

    def test_csrf_and_foreign_origin(self):
        self.assertEqual(self.client.post('/api/cases/demo').status_code,403)
        self.assertEqual(self.client.post('/api/cases/demo',headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)

    def test_persistence_and_optimistic_version(self):
        d=sample().model_dump(mode='json');d['title']='Módosított'
        r=self.client.put('/api/cases/'+self.cid,json={'data':d,'version':1},headers=self.headers)
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['version'],2)
        self.assertEqual(self.client.put('/api/cases/'+self.cid,json={'data':d,'version':1},headers=self.headers).status_code,409)
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['data']['title'],'Módosított')
        old=self.client.get(f'/api/cases/{self.cid}/versions/1').json();self.assertEqual(old['data']['title'],'Tesztvizsgálat')

    def test_approval_and_report_consistency(self):
        r=self.client.post(f'/api/cases/{self.cid}/approve',json={'version':1,'financials':True,'relationships':True,'rules':True},headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        export=self.client.get(f'/api/cases/{self.cid}/report/docx');self.assertEqual(export.status_code,200)
        doc=Document(BytesIO(export.content));text='\n'.join(p.text for p in doc.paragraphs)
        self.assertIn('Mikrovállalkozás',text);self.assertNotIn('TERVEZET',text);self.assertIn('Teszt Szakértő',text)
        data=sample().model_dump(mode='json');data['title']='Új változat'
        self.client.put('/api/cases/'+self.cid,json={'data':data,'version':1},headers=self.headers)
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['status'],'draft')
        old=self.client.get(f'/api/cases/{self.cid}/versions/1').json();self.assertIsNotNone(old['approved_at'])

    def test_report_preview_uses_current_saved_version(self):
        preview=self.client.get(f'/api/cases/{self.cid}/report-summary').json()
        self.assertFalse(preview['approved']);self.assertEqual(preview['version'],1)
        self.assertIn('jóváhagyásra váró',preview['conclusion'])
        data=sample().model_dump(mode='json');data['companies'][0]['name']='Új név Kft.'
        self.client.put(f'/api/cases/{self.cid}',json={'data':data,'version':1},headers=self.headers)
        preview=self.client.get(f'/api/cases/{self.cid}/report-summary').json()
        self.assertEqual(preview['company'],'Új név Kft.');self.assertEqual(preview['version'],2)

    def test_unresolved_case_cannot_be_approved(self):
        r=self.client.post('/api/cases/demo',headers=self.headers);cid=r.json()['id']
        r=self.client.post(f'/api/cases/{cid}/approve',json={'version':1,'financials':True,'relationships':True,'rules':True},headers=self.headers)
        self.assertEqual(r.status_code,422)

    def test_client_scope_and_internal_data_protection(self):
        r=self.client.post('/api/users',json={'name':'Ügyfél','username':'customer','password':self.password,'role':'client'},headers=self.headers);uid=r.json()['id']
        other=self.client.post('/api/cases',json={'data':sample().model_dump(mode='json')},headers=self.headers).json()['id']
        self.client.put(f'/api/cases/{self.cid}',json={'data':sample().model_dump(mode='json'),'version':1,'client_user_id':uid},headers=self.headers)
        customer=TestClient(app);login=customer.post('/api/auth/login',json={'username':'customer','password':self.password});ch={'X-CSRF-Token':login.json()['csrf']}
        self.assertEqual(customer.get('/api/cases/'+other).status_code,404)
        result=customer.get('/api/cases/'+self.cid).json();self.assertNotIn('data',result);self.assertNotIn('calculation',result)
        self.assertEqual(customer.get(f'/api/cases/{self.cid}/calculate').status_code,403)
        self.assertEqual(customer.get(f'/api/cases/{self.cid}/report-summary').status_code,403)
        self.assertEqual(customer.get(f'/api/cases/{self.cid}/report/docx').status_code,404)
        self.assertEqual(customer.post('/api/cases/demo',headers=ch).status_code,403)
        self.assertEqual(len(customer.get('/api/cases').json()),1)
        self.client.post(f'/api/cases/{self.cid}/approve',json={'version':2,'financials':True,'relationships':True,'rules':True},headers=self.headers)
        result=customer.get('/api/cases/'+self.cid).json();self.assertEqual(result['status'],'approved');self.assertIn('totals',result)
        self.assertEqual(customer.get(f'/api/cases/{self.cid}/report/docx').status_code,200)
        self.assertEqual(customer.post('/api/cases/'+self.cid+'/intake',json={'message':'Új tulajdonosi adat érkezett.'},headers=ch).status_code,200)
        customer.close()

    def test_analyst_cannot_approve(self):
        self.client.post('/api/users',json={'name':'Elemző','username':'analyst','password':self.password,'role':'analyst'},headers=self.headers)
        analyst=TestClient(app);r=analyst.post('/api/auth/login',json={'username':'analyst','password':self.password});h={'X-CSRF-Token':r.json()['csrf']}
        self.assertEqual(analyst.post(f'/api/cases/{self.cid}/approve',json={'version':1,'financials':True,'relationships':True,'rules':True},headers=h).status_code,403)
        analyst.close()

    def test_upload_download_and_audit(self):
        r=self.client.post(f'/api/cases/{self.cid}/documents',files={'file':('forras.txt',b'evidence','text/plain')},headers=self.headers)
        self.assertEqual(r.status_code,200);did=r.json()['id']
        self.assertEqual(self.client.get(f'/api/cases/{self.cid}/documents/{did}').content,b'evidence')
        docs=self.client.get(f'/api/cases/{self.cid}/documents').json();self.assertEqual(len(docs[0]['sha256']),64)
        self.assertIn('document_uploaded',[r['action'] for r in self.client.get(f'/api/cases/{self.cid}/audit').json()])
        self.assertEqual(self.client.post(f'/api/cases/{self.cid}/documents',files={'file':('bad.html',b'<script/>','text/html')},headers=self.headers).status_code,422)

    def test_bad_input_and_no_password_echo(self):
        r=self.client.post('/api/users',json={'name':'T','username':'x','password':'short'},headers=self.headers)
        self.assertEqual(r.status_code,422);self.assertNotIn('short',r.text)
        d=sample().model_dump(mode='json');d['financials'][0]['employees']='NaN'
        self.assertEqual(self.client.post('/api/cases',json={'data':d},headers=self.headers).status_code,422)

    def test_pending_client_answers_block_finalization(self):
        self.client.post(f'/api/cases/{self.cid}/intake',json={'message':'Új adat, ellenőrzendő.'},headers=self.headers)
        p={'version':1,'financials':True,'relationships':True,'rules':True}
        self.assertEqual(self.client.post(f'/api/cases/{self.cid}/approve',json=p,headers=self.headers).status_code,422)
        iid=self.client.get(f'/api/cases/{self.cid}/intake').json()[0]['id']
        self.client.post(f'/api/cases/{self.cid}/intake/{iid}/review',headers=self.headers)
        self.assertEqual(self.client.post(f'/api/cases/{self.cid}/approve',json=p,headers=self.headers).status_code,200)

    def test_mnb_response_uses_last_applicable_quote(self):
        inner='<MNBExchangeRates><Day date="2024-12-30"><Rate unit="1" curr="EUR">410,09</Rate></Day><Day date="2025-01-02"><Rate unit="1" curr="EUR">420,00</Rate></Day></MNBExchangeRates>'
        raw=('<Envelope><GetExchangeRatesResult>'+escape(inner)+'</GetExchangeRatesResult></Envelope>').encode()
        class Upstream:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,*args):return raw
        with patch('app.main.urlopen',return_value=Upstream()):
            r=self.client.get('/api/mnb?day=2024-12-31')
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['quoted'],'2024-12-30')
        self.assertEqual(r.json()['value'],'410.09')
        self.assertTrue(r.json()['confirmed'])

    def test_mnb_network_failure_has_manual_fallback_message(self):
        with patch('app.main.urlopen',side_effect=OSError('blocked')):
            r=self.client.get('/api/mnb?day=2024-12-31')
        self.assertEqual(r.status_code,502)
        self.assertIn('kézzel',r.json()['detail'])


if __name__=='__main__':unittest.main()
