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
from playwright.sync_api import sync_playwright

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
                    assert not errors,errors
                    print(json.dumps({'files':files,'modules':['tao','kkv'],'viewports':[360,390,768,1366,1440],'drag_drop':True,'edited_name':True,'source_staff_not_annual':True,'xlsx_download':True,'browser_errors':errors}))
                    browser.close()
            finally:
                server.terminate()
                try:server.wait(timeout=10)
                except subprocess.TimeoutExpired:server.kill();server.wait()
if __name__=='__main__':main()
