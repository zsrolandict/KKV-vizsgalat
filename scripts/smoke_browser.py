"""Isolated browser workflow. Never creates credentials or cases in the live database."""
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from docx import Document
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'test-results'
OUT.mkdir(exist_ok=True)
PORT=8011
URL=f'http://127.0.0.1:{PORT}'


def main():
    with tempfile.TemporaryDirectory(prefix='kkv-browser-') as folder:
        log=open(OUT/'browser-server.log','w')
        env={**os.environ,'KKV_DATA_DIR':folder,'XDG_CACHE_HOME':folder+'/cache'}
        server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            for _ in range(100):
                if server.poll() is not None:raise RuntimeError('A tesztkiszolgáló leállt.')
                try:
                    if urlopen(URL+'/api/health',timeout=1).status==200:break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('A tesztkiszolgáló nem indult el.')
            errors=[]
            password=secrets.token_urlsafe(24)
            with sync_playwright() as pw:
                executable=os.environ.get('KKV_CHROMIUM') or shutil.which('chromium') or shutil.which('google-chrome')
                browser=pw.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox'],env=env)
                context=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True,locale='hu-HU')
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(URL);page.locator('#auth-form').wait_for()
                page.screenshot(path=str(OUT/'01-elso-belepes.png'),full_page=True)
                page.locator('[name=name]').fill('Teszt Szakértő')
                page.locator('[name=username]').fill('expert')
                page.locator('[name=password]').fill(password)
                page.locator('#auth-form [type=submit]').click()
                page.get_by_role('heading',name='Ügyeid, egy helyen.').wait_for()
                page.locator('.hero [data-action=demo]').click()
                page.locator('.result-card h2').wait_for()
                assert page.locator('.result-card h2').inner_text()=='Középvállalkozás'
                page.screenshot(path=str(OUT/'02-attekintes.png'),full_page=True)
                page.locator('.tabs [data-action=tab][data-tab=calculation]').click()
                page.locator('.calculation-total').wait_for()
                assert '140,5' in page.locator('.calculation-total').inner_text()
                page.screenshot(path=str(OUT/'03-szamitas.png'),full_page=True)
                page.locator('#scenario').select_option('all')
                expect(page.locator('.calculation-total td').nth(3)).to_have_text('183')
                assert '183' in page.locator('.calculation-total').inner_text()
                page.locator('.tabs [data-action=tab][data-tab=graph]').click()
                page.locator('.graph-node').first.wait_for()
                page.screenshot(path=str(OUT/'04-ceghalo.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(OUT/'05-mobil.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.set_viewport_size({'width':1440,'height':1050})
                page.locator('.sidebar [data-action=new-case]').click()
                page.locator('#modal-form [name=name]').fill('Böngészőteszt Kft.')
                page.locator('#modal-form [name=title]').fill('Ellenőrzött mintavizsgálat')
                page.locator('#modal-form [type=submit]').click()
                page.get_by_role('heading',name='Böngészőteszt Kft.',exact=True).wait_for()
                cid=page.evaluate('S.cid')
                page.locator('.tabs [data-action=tab][data-tab=financials]').click()
                page.locator('[data-fin=employees]').wait_for()
                for year in [2025,2024]:
                    page.locator(f'[data-action=year][data-year="{year}"]').click()
                    page.locator('[data-fin=employees]').fill('2')
                    page.locator('[data-fin=turnover]').fill('1000')
                    page.locator('[data-fin=balance]').fill('2000')
                    page.locator('[data-fin=accepted]').fill(f'{year+1}-05-31')
                    page.locator('[data-fin=source]').fill('Ellenőrzött tesztbeszámoló')
                    page.locator('[data-rate=value]').fill('400')
                    page.locator('[data-rate=quoted]').fill(f'{year}-12-31')
                    page.locator('[data-rate=source]').fill('MNB – tesztforrás')
                    page.locator('[data-rate=confirmed]').check()
                page.locator('[data-action=save]').click()
                expect(page.locator('[data-action=save]')).to_be_disabled(); assert page.locator('.tabs .tab-badge').count()==0
                page.locator('.tabs [data-action=tab][data-tab=review]').click()
                page.locator('#approval-form').wait_for()
                for name in ['financials','relationships','rules']:page.locator(f'#approval-form [name={name}]').check()
                page.locator('#approval-form [type=submit]').click()
                page.locator('.approval-card .banner.green').wait_for()
                page.locator('.tabs [data-action=tab][data-tab=documents]').click()
                page.locator('[data-action=export][data-kind=docx]').wait_for()
                with page.expect_download() as event:page.locator('[data-action=export][data-kind=docx]').click()
                download=event.value;path=OUT/'smoke-allasfoglalas.docx';download.save_as(path)
                doc=Document(path);text='\n'.join(p.text for p in doc.paragraphs)
                assert 'Mikrovállalkozás' in text and 'Böngészőteszt Kft.' in text and 'TERVEZET' not in text
                with page.expect_download(timeout=90000) as event:page.locator('[data-action=export][data-kind=pdf]').click()
                event.value.save_as(OUT/'smoke-allasfoglalas.pdf')
                assert (OUT/'smoke-allasfoglalas.pdf').read_bytes().startswith(b'%PDF')
                page.screenshot(path=str(OUT/'06-jovahagyott-allasfoglalas.png'),full_page=True)
                with page.expect_download() as event:page.locator('.sidebar [data-action=template]').click()
                event.value.save_as(OUT/'adatbekeres.xlsx')
                page.locator('.sidebar [data-action=users]').click()
                page.get_by_role('heading',name='Munkatársak és ügyfelek.').wait_for()
                page.locator('[data-action=new-user]').click()
                page.locator('#modal-form [name=name]').fill('Teszt Ügyfél')
                page.locator('#modal-form [name=username]').fill('customer')
                page.locator('#modal-form [name=password]').fill(password)
                page.locator('#modal-form [name=role]').select_option('client')
                page.locator('#modal-form [type=submit]').click()
                page.get_by_text('Teszt Ügyfél',exact=True).wait_for()
                page.goto(URL+f'/#case/{cid}/overview')
                page.get_by_role('heading',name='Böngészőteszt Kft.',exact=True).wait_for()
                page.locator('.case-heading [data-action=case-settings]').click()
                uid=page.locator('[name=client_user_id] option').filter(has_text='Teszt Ügyfél').get_attribute('value')
                page.locator('[name=client_user_id]').select_option(uid)
                page.locator('#modal-form [type=submit]').click()
                page.locator('[data-action=save]').click();expect(page.locator('[data-action=save]')).to_be_disabled()
                customer_context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True,locale='hu-HU')
                customer=customer_context.new_page();customer.on('pageerror',lambda e:errors.append(str(e)))
                customer.goto(URL);customer.locator('[name=username]').fill('customer');customer.locator('[name=password]').fill(password)
                customer.locator('#auth-form [type=submit]').click();customer.get_by_role('heading',name='A vállalkozásod vizsgálatai.').wait_for()
                assert customer.locator('.case-row').count()==1
                customer.locator('.case-row').click();customer.locator('.client-intro').wait_for()
                assert customer.locator('[data-action=client-export]').count()==2
                customer.locator('#intake-form [name=message]').fill('A tulajdonosi arányokat a csatolt dokumentum szerint kérjük ellenőrizni.')
                customer.locator('#intake-form [type=submit]').click();customer.locator('.intake-message').wait_for()
                customer.screenshot(path=str(OUT/'07-ugyfelnezet.png'),full_page=True)
                assert not errors,errors
                customer_context.close();context.close();browser.close()
            print('Böngészőteszt sikeres: első fiók, mintaszámítás, teljes forgatókönyv, mobil nézet, adatbevitel, jóváhagyás, Word/PDF, sablon, ügyfélhozzáférés és adatbekérés.')
            print('Képernyőképek és tesztdokumentumok: test-results/')
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
            log.close()


if __name__=='__main__':main()
