import copy
import json
import os
import secrets
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app import db
from app.main import app
from app.assistant_api import Answer, Change, proposal, ai_answer, Message
from .helpers import sample, extended


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'KKV_DATA_DIR':self.tmp.name,'OPENAI_API_KEY':'','OPENAI_MODEL':'','GEMINI_API_KEY':'','GEMINI_MODEL':'','KKV_AI_PROVIDER':''});self.env.start();db.initialize()
        self.client=TestClient(app)
        auth=self.client.post('/api/auth/setup',json={'name':'Tesztelő','username':'expert','password':secrets.token_urlsafe(24)}).json()
        self.headers={'X-CSRF-Token':auth['csrf']}
        self.cid=self.client.post('/api/cases',json={'data':sample().model_dump(mode='json')},headers=self.headers).json()['id']

    def tearDown(self):
        self.client.close();self.env.stop();self.tmp.cleanup()

    def discuss(self,module='kkv',cid=None,use_ai=False):
        return self.client.post(f'/api/assistant/{module}/{cid or self.cid}',json={'messages':[{'role':'user','content':'Miért nem dönthető el a kapcsolat?'}],'use_ai':use_ai},headers=self.headers)

    def test_local_explanation_and_missing_key(self):
        local=self.discuss().json();self.assertEqual(local['mode'],'local');self.assertFalse(local['changes'])
        self.assertEqual(self.discuss(use_ai=True).status_code,409)
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['version'],1)

    def test_key_is_not_returned_and_csrf_required(self):
        self.assertEqual(self.client.post('/api/assistant/settings',json={'api_key':'test-secret'}).status_code,403)
        saved=self.client.post('/api/assistant/settings',json={'api_key':'test-secret'},headers=self.headers)
        self.assertEqual(saved.status_code,200)
        self.assertNotIn('test-secret',self.client.get('/api/assistant/settings').text)
        self.client.post('/api/assistant/settings',json={'clear':True},headers=self.headers)
        self.assertFalse(self.client.get('/api/assistant/settings').json()['configured'])

    def test_proposal_does_not_save_until_normal_versioned_put(self):
        answer=Answer(answer='A nyilatkozat alapján feltételezést rögzítenék.',changes=[Change(field='assumptions',value='Megbízói nyilatkozat, még ellenőrizendő.',explanation='A megadott nyilatkozat elkülönítése.')])
        with patch('app.assistant_api.ai_answer',new=AsyncMock(return_value=answer)):
            response=self.discuss(use_ai=True).json()
        current=self.client.get('/api/cases/'+self.cid).json()
        self.assertEqual(current['data']['assumptions'],'')
        saved=self.client.put('/api/cases/'+self.cid,json={'data':response['proposed_data'],'version':response['base_version']},headers=self.headers)
        self.assertEqual(saved.status_code,200)
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['data']['assumptions'],answer.changes[0].value)
        self.assertEqual(self.client.put('/api/cases/'+self.cid,json={'data':response['proposed_data'],'version':1},headers=self.headers).status_code,409)

    def test_invalid_and_unsupported_ai_edits_are_not_applicable(self):
        for change in [Change(field='root',value='unknown',explanation='bad'),Change(field='rates',item={'year':2024,'date':'224420-02-04','value':'410'},explanation='bad')]:
            with patch('app.assistant_api.ai_answer',new=AsyncMock(return_value=Answer(answer='Javaslat',changes=[change]))):
                result=self.discuss(use_ai=True).json()
            self.assertIsNone(result['proposed_data']);self.assertEqual(result['changes'],[])
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['version'],1)

    def test_ai_cannot_confirm_decisions(self):
        raw=extended(['b'],[]).model_dump(mode='json')
        change=Change(field='decisions',item={'id':'d','first':'a','second':'b','relation':'linked','confirmed':True,'confirmed_years':[2024,2025],'source':'nyilatkozat','reason':'felhasználói válasz'},explanation='tervezet')
        data,_=proposal('kkv',raw,[change]);self.assertFalse(data['decisions'][0]['confirmed']);self.assertEqual(data['decisions'][0]['confirmed_years'],[])

    def test_tao_discussion_and_proposal_are_separate_from_kkv(self):
        raw={'title':'Tao teszt','as_of':'2026-10-10','companies':[{'id':'a','name':'Alfa'},{'id':'b','name':'Beta'}]}
        cid=self.client.post('/api/tao/cases',json={'data':raw},headers=self.headers).json()['id']
        self.assertIn('Alfa ↔ Beta',self.discuss('tao',cid).json()['answer'])
        answer=Answer(answer='Döntési tervezet.',changes=[Change(field='decisions',item={'first':'a','second':'b','as_of':'2026-10-10','result':'related','confirmed':True,'basis':'Tao','reason':'nyilatkozat','evidence':{'source':'Nyilatkozat'}},explanation='nem ellenőrzött')])
        with patch('app.assistant_api.ai_answer',new=AsyncMock(return_value=answer)):
            response=self.discuss('tao',cid,True).json()
        self.assertFalse(response['proposed_data']['decisions'][0]['confirmed'])
        self.assertEqual(self.client.get('/api/tao/cases/'+cid).json()['version'],1)

    def test_client_cannot_use_assistant(self):
        self.client.post('/api/users',json={'name':'Ügyfél','username':'client','password':secrets.token_urlsafe(24),'role':'client'},headers=self.headers)
        with db.connection() as con:con.execute('UPDATE users SET role=? WHERE username=?',('client','expert'))
        self.assertEqual(self.discuss().status_code,403)
        self.assertEqual(self.client.get('/api/assistant/settings').status_code,403)

    def test_provider_adapter_uses_json_and_does_not_leak_errors(self):
        self.client.post('/api/assistant/settings',json={'api_key':'test-secret'},headers=self.headers)
        transport=AsyncMock()
        response=unittest.mock.Mock(status_code=200)
        response.json.return_value={'choices':[{'message':{'content':json.dumps({'answer':'Pontosítsd a forrást.','changes':[]})}}]}
        transport.post.return_value=response
        with patch('app.assistant_api.httpx.AsyncClient') as factory:
            factory.return_value.__aenter__.return_value=transport
            result=self.discuss(use_ai=True)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['answer'],'Pontosítsd a forrást.')
        call=transport.post.call_args
        self.assertEqual(call.args[0],'https://api.openai.com/v1/chat/completions')
        self.assertEqual(call.kwargs['json']['response_format']['type'],'json_object')
        response.status_code=401
        with patch('app.assistant_api.httpx.AsyncClient') as factory:
            factory.return_value.__aenter__.return_value=transport
            failure=self.discuss(use_ai=True)
        self.assertEqual(failure.status_code,502)
        self.assertNotIn('test-secret',failure.text)
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['version'],1)

    def test_environment_secret_is_not_copied_into_saved_settings(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'injected-secret'}):
            result=self.client.post('/api/assistant/settings',json={'model':'gpt-4.1-mini'},headers=self.headers)
            self.assertEqual(result.status_code,200)
            text=(db.data_dir()/'ai-settings.json').read_text()
            self.assertNotIn('injected-secret',text)

    def test_gemini_native_api_request_and_json_response(self):
        self.client.post('/api/assistant/settings',json={'provider':'gemini','api_key':'gemini-test-secret'},headers=self.headers)
        settings=self.client.get('/api/assistant/settings').json()
        self.assertEqual(settings['provider'],'gemini')
        self.assertEqual(settings['model'],'gemini-2.5-flash')
        self.assertNotIn('gemini-test-secret',str(settings))
        transport=AsyncMock()
        response=unittest.mock.Mock(status_code=200)
        response.json.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'internal'},{'text':json.dumps({'answer':'A forrás és a rokonság pontosítása kell.','changes':[{'field':'assumptions','value':'Felhasználói nyilatkozat.','explanation':'A válasz rögzítése.'}]})}]}}]}
        transport.post.return_value=response
        with patch('app.assistant_api.httpx.AsyncClient') as factory:
            factory.return_value.__aenter__.return_value=transport
            result=self.discuss(use_ai=True)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['proposed_data']['assumptions'],'Felhasználói nyilatkozat.')
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['data']['assumptions'],'')
        call=transport.post.call_args
        self.assertEqual(call.args[0],'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent')
        self.assertNotIn('gemini-test-secret',call.args[0])
        self.assertEqual(call.kwargs['headers']['x-goog-api-key'],'gemini-test-secret')
        payload=call.kwargs['json']
        self.assertEqual(payload['generationConfig']['responseMimeType'],'application/json')
        self.assertEqual(len(payload['contents']),1)
        self.assertEqual(len(payload['contents'][0]['parts']),2)
        self.assertIn('systemInstruction',payload)

    def test_gemini_blocked_or_truncated_response_never_applies(self):
        self.client.post('/api/assistant/settings',json={'provider':'gemini','api_key':'gemini-test-secret'},headers=self.headers)
        transport=AsyncMock();response=unittest.mock.Mock(status_code=200);transport.post.return_value=response
        for body in [{'candidates':[],'promptFeedback':{'blockReason':'SAFETY'}},{'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'incomplete'}]}}]}]:
            response.json.return_value=body
            with patch('app.assistant_api.httpx.AsyncClient') as factory:
                factory.return_value.__aenter__.return_value=transport
                failure=self.discuss(use_ai=True)
            self.assertEqual(failure.status_code,502)
            self.assertIn('nem adott teljes választ',failure.text)
            self.assertNotIn('gemini-test-secret',failure.text)
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['version'],1)

    def test_provider_switch_cannot_reuse_the_other_provider_key(self):
        self.client.post('/api/assistant/settings',json={'provider':'openai','api_key':'openai-test-secret'},headers=self.headers)
        self.client.post('/api/assistant/settings',json={'provider':'gemini'},headers=self.headers)
        settings=self.client.get('/api/assistant/settings').json()
        self.assertEqual(settings['provider'],'gemini');self.assertFalse(settings['configured'])
        self.assertNotIn('openai-test-secret',(db.data_dir()/'ai-settings.json').read_text())

    def test_legacy_openai_settings_and_provider_specific_environment(self):
        (db.data_dir()/'ai-settings.json').write_text(json.dumps({'api_key':'legacy-secret','model':'gpt-4.1-mini'}))
        self.assertEqual(self.client.get('/api/assistant/settings').json()['provider'],'openai')
        self.client.post('/api/assistant/settings',json={'provider':'gemini'},headers=self.headers)
        with patch.dict(os.environ,{'OPENAI_API_KEY':'unrelated-secret'}):
            self.assertFalse(self.client.get('/api/assistant/settings').json()['configured'])
        with patch.dict(os.environ,{'GEMINI_API_KEY':'injected-gemini-secret','GEMINI_MODEL':'gemini-custom'}):
            settings=self.client.get('/api/assistant/settings').json()
            self.assertTrue(settings['configured']);self.assertEqual(settings['model'],'gemini-custom')
            self.client.post('/api/assistant/settings',json={'provider':'gemini'},headers=self.headers)
            self.assertNotIn('injected-gemini-secret',(db.data_dir()/'ai-settings.json').read_text())

    def test_gemini_errors_identify_cause_without_returning_provider_text(self):
        self.client.post('/api/assistant/settings',json={'provider':'gemini','api_key':'gemini-test-secret'},headers=self.headers)
        cases=[(404,{'error':{'message':'model unavailable gemini-test-secret'}},'nem található'),
               (400,{'error':{'message':'secret gemini-test-secret','details':[{'reason':'API_KEY_INVALID'}]}},'érvénytelen'),
               (403,{'error':{'message':'secret gemini-test-secret'}},'hozzáférést'),
               (429,{'error':{'message':'secret gemini-test-secret'}},'keretet'),
               (400,{'error':{'message':'User location is not supported for API use'}},'használat helyének'),
               (400,{'error':{'message':'secret gemini-test-secret'}},'beállításait'),
               (503,{'error':{'message':'secret gemini-test-secret'}},'átmeneti')]
        for status,body,hint in cases:
            with self.subTest(status=status,hint=hint):
                transport=AsyncMock();response=unittest.mock.Mock(status_code=status);response.json.return_value=body;transport.post.return_value=response
                with patch('app.assistant_api.httpx.AsyncClient') as factory:
                    factory.return_value.__aenter__.return_value=transport
                    result=self.discuss(use_ai=True)
                self.assertEqual(result.status_code,502)
                self.assertIn(f'HTTP {status}',result.json()['detail']);self.assertIn(hint,result.json()['detail'])
                self.assertNotIn('gemini-test-secret',result.text)
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['version'],1)

    def test_gemini_model_discovery_filters_and_paginates_without_sending_case(self):
        self.client.post('/api/assistant/settings',json={'provider':'gemini','api_key':'gemini-test-secret','model':'gemini-unavailable'},headers=self.headers)
        first=unittest.mock.Mock(status_code=200);first.json.return_value={'models':[
            {'name':'models/gemini-available','displayName':'Gemini available','supportedGenerationMethods':['generateContent']},
            {'name':'models/gemini-image-preview','supportedGenerationMethods':['generateContent']},
            {'name':'models/gemini-embedding','supportedGenerationMethods':['embedContent']}], 'nextPageToken':'page-two'}
        second=unittest.mock.Mock(status_code=200);second.json.return_value={'models':[{'name':'models/gemini-another','supportedGenerationMethods':['generateContent']}]}
        transport=AsyncMock();transport.get.side_effect=[first,second]
        with patch('app.assistant_api.httpx.AsyncClient') as factory:
            factory.return_value.__aenter__.return_value=transport
            result=self.client.get('/api/assistant/models')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual([v['id'] for v in result.json()['models']],['gemini-another','gemini-available'])
        self.assertFalse(result.json()['current_available'])
        self.assertNotIn('gemini-test-secret',result.text)
        call=transport.get.call_args
        self.assertEqual(call.kwargs['params']['pageToken'],'page-two')
        self.assertNotIn('json',call.kwargs);self.assertNotIn('gemini-test-secret',call.args[0])
        self.assertEqual(self.client.get('/api/assistant/settings').json()['model'],'gemini-unavailable')
        self.assertEqual(self.client.get('/api/cases/'+self.cid).json()['version'],1)

    def test_model_discovery_requires_key_and_handles_provider_rejection(self):
        self.client.post('/api/assistant/settings',json={'provider':'gemini'},headers=self.headers)
        self.assertEqual(self.client.get('/api/assistant/models').status_code,409)
        self.client.post('/api/assistant/settings',json={'provider':'gemini','api_key':'gemini-test-secret'},headers=self.headers)
        transport=AsyncMock();response=unittest.mock.Mock(status_code=403);response.json.return_value={'error':{'message':'gemini-test-secret'}};transport.get.return_value=response
        with patch('app.assistant_api.httpx.AsyncClient') as factory:
            factory.return_value.__aenter__.return_value=transport
            failure=self.client.get('/api/assistant/models')
        self.assertEqual(failure.status_code,502);self.assertIn('HTTP 403',failure.text);self.assertNotIn('gemini-test-secret',failure.text)
        with db.connection() as con:con.execute('UPDATE users SET role=? WHERE username=?',('analyst','expert'))
        self.assertEqual(self.client.get('/api/assistant/models').status_code,403)

    def test_invalid_date_error_is_readable(self):
        raw=sample().model_dump(mode='json');raw['rates'][0]['quoted']='224420-02-04'
        result=self.client.put('/api/cases/'+self.cid,json={'data':raw,'version':1},headers=self.headers)
        self.assertEqual(result.status_code,422)
        self.assertIn('négyjegyű',result.text)
