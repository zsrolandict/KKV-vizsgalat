"""Isolated PDF → review/edit → Tao/KKV workflow. Optional real OPTEN source directory."""
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
URL='http://127.0.0.1:8012'

def main():
    sources=[Path(p) for p in sys.argv[1:]]
    if not sources:
        raise SystemExit('Usage: .venv/bin/python scripts/smoke_pdf_browser.py <OPTEN PDF> ...')
    with tempfile.TemporaryDirectory(prefix='kkv-pdf-browser-') as folder:
        env={**os.environ,'KKV_DATA_DIR':folder,'XDG_CACHE_HOME':folder+'/cache'}
        with open(OUT/'pdf-browser-server.log','w') as log:
            server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8012'],cwd=ROOT,env=env,stdout=log,stderr=log)
            try:
                for _ in range(100):
                    if server.poll() is not None:raise RuntimeError('Server stopped')
                    try:
                        if urlopen(URL+'/api/health',timeout=1).status==200:break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError('Server not ready')
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'],env=env)
                    context=browser.new_context(viewport={'width':1440,'height':1000},locale='hu-HU',accept_downloads=True)
                    password=secrets.token_urlsafe(24)
                    setup=context.request.post(URL+'/api/auth/setup',data={'name':'Böngészőteszt','username':'expert','password':password})
                    assert setup.status==200,setup.text()
                    page=context.new_page(); errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(URL+'/pdf-import?module=tao');page.locator('#dropzone').wait_for()
                    # Exercise the actual drop handler with browser File objects, not only file selection.
                    dropped=[]
                    for path in sources:
                        import base64
                        dropped.append({'name':path.name,'data':base64.b64encode(path.read_bytes()).decode()})
                    page.evaluate('''items=>{const transfer=new DataTransfer();for(const f of items){const raw=Uint8Array.from(atob(f.data),c=>c.charCodeAt(0));transfer.items.add(new File([raw],f.name,{type:'application/pdf'}));}document.querySelector('#dropzone').dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer}));}''',dropped)
                    page.locator('#review-form').wait_for(timeout=120000)
                    assert page.locator('.import-error').all_text_contents()==[''],page.locator('.import-error').all_text_contents()
                    files=page.evaluate("document.querySelectorAll('[data-include]').length")
                    assert files==len(sources),(files,len(sources))
                    # Edit extracted name, open source detail, keyboard interaction, no annual staff autofill.
                    name=page.locator('[data-path="0.name"]');name.fill('Böngészőteszt · ellenőrzött cégnév')
                    page.locator('.candidate details').first.locator('summary').focus();page.keyboard.press('Enter')
                    assert page.locator('.candidate details').first.get_attribute('open') is not None
                    assert page.locator('[data-path="0.financials.0.employees"]').input_value()==''
                    for width in [360,390,768,1366,1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
                        assert not overflow,f'Import horizontal overflow at {width}'
                        page.screenshot(path=str(OUT/f'pdf-review-{width}.png'),full_page=False)
                    page.locator('#asof').fill('2024-12-31');page.locator('#title').fill('PDF → Tao böngészőteszt')
                    page.locator('#confirmed').check();page.locator('#apply').click()
                    page.locator('#result a').wait_for(timeout=30000)
                    tao_link=page.locator('#result a').get_attribute('href')
                    page.locator('#module').select_option('kkv');page.locator('#title').fill('PDF → KKV böngészőteszt')
                    page.locator('#apply').click();page.locator('#result').get_by_text('A KKV-tervezet elkészült.',exact=False).wait_for(timeout=30000)
                    kkv_link=page.locator('#result a').get_attribute('href')
                    page.goto(URL+tao_link);page.get_by_role('heading',name='PDF → Tao böngészőteszt',exact=True).wait_for()
                    for width in [360,390,768,1366,1440]:
                        page.set_viewport_size({'width':width,'height':1000});assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),f'Tao overflow at {width}'
                        page.screenshot(path=str(OUT/f'tao-matrix-{width}.png'))
                    with page.expect_download() as download:
                        page.get_by_role('button',name='XLSX',exact=True).click()
                    assert Path(download.value.path()).stat().st_size>1000
                    page.goto(URL+kkv_link);page.get_by_role('heading',name='Böngészőteszt · ellenőrzött cégnév',exact=True).wait_for()
                    assert page.get_by_text('Előzetes eredmény',exact=False).count()>0
                    # Refresh existing cases with the same PDFs, selecting only an explicit name correction.
                    for module, link in [('tao',tao_link),('kkv',kkv_link)]:
                        cid=link.split('case=')[-1] if module=='tao' else link.split('/')[2]
                        base=URL+('/api/tao/cases/' if module=='tao' else '/api/cases/')+cid
                        before=context.request.get(base).json()
                        page.goto(URL+'/pdf-import?module='+module)
                        page.locator('#files').set_input_files([str(p) for p in sources])
                        page.locator('#review-form').wait_for(timeout=120000)
                        page.locator('[data-path="0.name"]').fill('PDF-frissítéssel ellenőrzött név')
                        page.locator('#target-case').select_option(cid)
                        expect(page.locator("#title")).to_be_disabled()
                        page.locator('#confirmed').check();page.locator('#apply').click()
                        page.locator('#merge-confirm').wait_for()
                        assert page.locator('[data-operation]:checked').count()==0
                        changed=page.locator('#comparison section').filter(has_text='PDF-frissítéssel ellenőrzött név').first
                        changed.locator('[data-operation]').check()
                        for width in [360,390,768,1366,1440]:
                            page.set_viewport_size({'width':width,'height':1000})
                            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),f'Merge overflow at {width}'
                        page.locator('#merge-confirm').check();page.locator('#merge-apply').click()
                        page.locator('#result a').wait_for(timeout=30000)
                        after=context.request.get(base).json()
                        assert after['version']==before['version']+1
                        assert any(c['name']=='PDF-frissítéssel ellenőrzött név' for c in after['data']['companies'])
                        prior=context.request.get(base+'/versions/'+str(before['version'])).json()
                        assert prior['data']==before['data']
                    chain = {'title':'Közvetett befolyás böngészőteszt','as_of':'2025-12-31',
                             'companies':[{'id':v,'name':v.upper()} for v in ['a','b','c']],
                             'voting_facts':[{'id':str(i),'owner':owner,'company':target,'capital':'60',
                                              'valid_from':'2024-01-01','evidence':{'source':'Fiktív szavazati forrás'}}
                                             for i,(owner,target) in enumerate([('a','b'),('b','c')])]}
                    response=context.request.post(URL+'/api/tao/cases',data={'data':chain},headers={'X-CSRF-Token':setup.json()['csrf']})
                    assert response.status==200,response.text()
                    page.goto(URL+'/tao?case='+response.json()['id'])
                    page.get_by_role('heading',name=chain['title'],exact=True).wait_for()
                    page.locator('.matrix [data-action=pair][data-index="1"]').first.click()
                    detail=page.locator('#pair-detail')
                    assert 'A → C: 60%' in detail.inner_text(),detail.inner_text()
                    assert 'A → B' in detail.inner_text() and 'B → C' in detail.inner_text()
                    for width in [360,390,768,1366,1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),f'Influence overflow at {width}'
                    from openpyxl import load_workbook
                    from io import BytesIO
                    export=context.request.get(URL+'/api/tao/cases/'+response.json()['id']+'/report/xlsx')
                    book=load_workbook(BytesIO(export.body()))
                    assert 'Befolyásszámítás' in book.sheetnames
                    assert any(row[2]=='A' and row[3]=='C' and row[4]=='60%' for row in book['Befolyásszámítás'].iter_rows(min_row=2,values_only=True))
                    family_data = {'title':'Rokonság böngészőteszt','as_of':'2025-12-31',
                                   'companies':[{'id':v,'name':v.upper()} for v in ['a','b']],
                                   'persons':[{'id':v,'name':v.upper()} for v in ['p','q']],
                                   'voting_facts':[{'id':str(i),'owner':owner,'company':target,'capital':capital,
                                                    'valid_from':'2024-01-01'}
                                                   for i,(owner,target,capital) in enumerate([('p','a','45'),('q','a','6'),('p','b','45'),('q','b','6')])]}
                    response=context.request.post(URL+'/api/tao/cases',data={'data':family_data},headers={'X-CSRF-Token':setup.json()['csrf']})
                    assert response.status==200,response.text()
                    family_id=response.json()['id']
                    page.goto(URL+'/tao?case='+family_id)
                    page.get_by_role('heading',name=family_data['title'],exact=True).wait_for()
                    page.locator('.tabs [data-tab="data"]').click()
                    page.get_by_role('button',name='Rokonság rögzítése',exact=True).click()
                    form=page.locator('#editor-form')
                    form.locator('[name=confirmed]').check()
                    form.locator('[type=submit]').click()
                    page.locator('#editor-error').wait_for()
                    assert 'forrás' in page.locator('#editor-error').inner_text()
                    form.locator('[name=source]').fill('Ellenőrzött házastársi nyilatkozat')
                    form.locator('[type=submit]').click()
                    page.locator('#editor').wait_for(state='hidden')
                    page.locator('.tabs [data-tab="matrix"]').click()
                    detail=page.locator('#pair-detail')
                    assert 'P + Q → A: 51%' in detail.inner_text(),detail.inner_text()
                    assert 'Ellenőrzött házastársi nyilatkozat' in detail.inner_text()
                    for width in [360,390,768,1366,1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),f'Family overflow at {width}'
                    export=context.request.get(URL+'/api/tao/cases/'+family_id+'/report/xlsx')
                    book=load_workbook(BytesIO(export.body()))
                    assert any('Ellenőrzött házastársi nyilatkozat' in str(v) for r in book['Rokonsági források'] for v in [c.value for c in r])
                    from docx import Document
                    report=context.request.get(URL+'/api/tao/cases/'+family_id+'/report/docx')
                    assert 'Igazolt rokonság: P – Q' in '\n'.join(p.text for p in Document(BytesIO(report.body())).paragraphs)
                    control_data={'title':'Irányítás böngészőteszt','as_of':'2025-12-31',
                                  'companies':[{'id':v,'name':v.upper()} for v in ['a','b','c']],
                                  'persons':[{'id':'p','name':'Közös Vezető'}]}
                    response=context.request.post(URL+'/api/tao/cases',data={'data':control_data},headers={'X-CSRF-Token':setup.json()['csrf']})
                    assert response.status==200,response.text();control_id=response.json()['id']
                    page.goto(URL+'/tao?case='+control_id)
                    page.get_by_role('heading',name=control_data['title'],exact=True).wait_for()
                    page.locator('.tabs [data-tab="data"]').click()
                    page.get_by_role('button',name='Ügyvezetési tény rögzítése',exact=True).click()
                    form=page.locator('#editor-form')
                    form.locator('[name=manager-p]').check()
                    form.locator('[name=common_management]').select_option('yes')
                    form.locator('[name=reason]').fill('Azonos ügyvezető; a tényleges döntési rend még tisztázandó.')
                    form.locator('[name=source]').fill('Ellenőrzött vezetői nyilatkozat')
                    form.locator('[name=confirmed]').check();form.locator('[type=submit]').click()
                    page.locator('#editor').wait_for(state='hidden')
                    current=context.request.get(URL+'/api/tao/cases/'+control_id).json()
                    assert not current['calculation']['rows'][0]['signals']
                    page.locator('[data-action="management"][data-id]').click()
                    form=page.locator('#editor-form')
                    form.locator('[name=business_control]').select_option('yes')
                    form.locator('[name=financial_control]').select_option('yes')
                    form.locator('[name=reason]').fill('Az üzleti és pénzügyi politika feletti döntő irányítás igazolt.')
                    form.locator('[type=submit]').click();page.locator('#editor').wait_for(state='hidden')
                    page.get_by_role('button',name='Irányítási jog rögzítése',exact=True).click()
                    form=page.locator('#editor-form')
                    form.locator('[name=company]').select_option('c')
                    form.locator('[name=membership]').select_option('member')
                    form.locator('[name=condition]').select_option('yes')
                    form.locator('[name=confirmed]').check();form.locator('[type=submit]').click()
                    page.locator('#editor-error').wait_for()
                    form.locator('[name=reason]').fill('A vezetők többségének megválasztási joga igazolt.')
                    form.locator('[name=source]').fill('Ellenőrzött társasági szerződés')
                    form.locator('[type=submit]').click();page.locator('#editor').wait_for(state='hidden')
                    current=context.request.get(URL+'/api/tao/cases/'+control_id).json()
                    assert current['calculation']['rows'][0]['stage']=='control_signal'
                    assert current['calculation']['rows'][1]['stage']=='control_signal'
                    assert not current['calculation']['rows'][2]['signals']
                    page.locator('.tabs [data-tab="matrix"]').click()
                    assert 'Ügyvezetési tények forrásai' in page.locator('#pair-detail').inner_text()
                    for width in [360,390,768,1366,1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),f'Control overflow at {width}'
                    export=context.request.get(URL+'/api/tao/cases/'+control_id+'/report/xlsx')
                    book=load_workbook(BytesIO(export.body()))
                    assert 'Irányítási jogok' in book.sheetnames and 'Ügyvezetési tények' in book.sheetnames
                    report=context.request.get(URL+'/api/tao/cases/'+control_id+'/report/docx')
                    text='\n'.join(p.text for p in Document(BytesIO(report.body())).paragraphs)
                    assert 'Irányítási tény: A → C' in text and 'Ügyvezetési tény: Közös Vezető' in text
                    if shutil.which('soffice'):
                        pdf=context.request.get(URL+'/api/tao/cases/'+control_id+'/report/pdf',timeout=90000)
                        assert pdf.status==200,pdf.text() if pdf.status!=200 else ''
                        assert pdf.body().startswith(b'%PDF')
                        extracted=subprocess.run([shutil.which('pdftotext'),'-','-'],input=pdf.body(),capture_output=True,check=True).stdout.decode('utf-8')
                        assert 'Ügyvezetési tény:' in extracted and 'Irányítási tény:' in extracted
                    special={'title':'BVK és telephely böngészőteszt','as_of':'2025-12-31',
                             'companies':[{'id':'a','name':'Fővállalkozás'},{'id':'pe','name':'Magyar telephely','entity_type':'permanent_establishment'},{'id':'b','name':'Portfóliócég'}],
                             'persons':[{'id':'p','name':'Vagyonkezelő személy'}]}
                    response=context.request.post(URL+'/api/tao/cases',data={'data':special},headers={'X-CSRF-Token':setup.json()['csrf']})
                    assert response.status==200,response.text();special_id=response.json()['id']
                    page.goto(URL+'/tao?case='+special_id)
                    page.get_by_role('heading',name=special['title'],exact=True).wait_for()
                    page.locator('.tabs [data-tab="data"]').click()
                    page.get_by_role('button',name='Telephelyi tény rögzítése',exact=True).click()
                    form=page.locator('#editor-form')
                    form.locator('[name=tax_status]').select_option('yes')
                    form.locator('[name=reason]').fill('Külföldi vállalkozó igazolt belföldi Tao-telephelye.')
                    form.locator('[name=source]').fill('Telephelyi adójogi nyilatkozat')
                    form.locator('[name=confirmed]').check();form.locator('[type=submit]').click()
                    page.locator('#editor').wait_for(state='hidden')
                    page.get_by_role('button',name='BVK-tény rögzítése',exact=True).click()
                    form=page.locator('#editor-form')
                    form.locator('[name=name]').fill('Teszt kezelt vagyon')
                    form.locator('[name=trustees-p]').check();form.locator('[name=holdings-b]').check()
                    form.locator('[name=reason]').fill('A szerződéses szerepek rögzítve, a joggyakorlás külön értékelve.')
                    form.locator('[name=source]').fill('BVK-szerződés')
                    form.locator('[name=confirmed]').check();form.locator('[name=rights_reviewed]').check()
                    for width in [360,390,768,1366,1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),f'BVK editor overflow at {width}'
                    form.locator('[type=submit]').click();page.locator('#editor').wait_for(state='hidden')
                    current=context.request.get(URL+'/api/tao/cases/'+special_id).json()
                    assert current['calculation']['rows'][0]['stage']=='special_signal'
                    assert not current['calculation']['rows'][1]['signals']
                    page.locator('.tabs [data-tab="matrix"]').click()
                    assert 'Telephelyi források' in page.locator('#pair-detail').inner_text()
                    export=context.request.get(URL+'/api/tao/cases/'+special_id+'/report/xlsx')
                    book=load_workbook(BytesIO(export.body()))
                    assert 'Tao-telephelyek' in book.sheetnames and 'BVK-tények' in book.sheetnames
                    report=context.request.get(URL+'/api/tao/cases/'+special_id+'/report/docx')
                    text='\n'.join(p.text for p in Document(BytesIO(report.body())).paragraphs)
                    assert 'Telephelyi tény:' in text and 'BVK: Teszt kezelt vagyon' in text
                    assert not errors,errors
                    print(json.dumps({'files':files,'modules':['tao','kkv'],'viewports':[360,390,768,1366,1440],'drag_drop':True,'edited_name':True,'source_staff_not_annual':True,'xlsx_download':True,'family_edit':True,'family_source_required':True,'family_exports':True,'control_edit':True,'management_conditions':True,'control_exports':True,'existing_case_merge':True,'bvk_editor':True,'pe_editor':True,'special_exports':True,'browser_errors':errors}))
                    browser.close()
            finally:
                server.terminate()
                try:server.wait(timeout=10)
                except subprocess.TimeoutExpired:server.kill();server.wait()
if __name__=='__main__':main()
