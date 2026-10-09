import hashlib
import hmac
import json
import os
import secrets
import subprocess
import tempfile
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
from xml.etree import ElementTree as ET

from fastapi import FastAPI, Request as WebRequest, HTTPException, Depends, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from . import db
from .demo import demonstration
from .engine import calculate, RULE_VERSION
from .importers import import_excel, template_bytes
from .models import Assessment
from .reports import word_report

db.initialize()
app=FastAPI(title='KKV – Szakértői műhely',version='1.0.0',docs_url=None,redoc_url=None,openapi_url=None)
STATIC=Path(__file__).parent/'static'
login_attempts=defaultdict(deque)


@app.middleware('http')
async def security(request, call_next):
    if request.method not in ['GET','HEAD','OPTIONS']:
        origin=request.headers.get('origin')
        if origin:
            parsed=urlsplit(origin)
            if parsed.netloc != request.headers.get('host') or parsed.scheme not in ['http','https']:
                return JSONResponse({'detail':'Idegen eredetű kérés nem engedélyezett.'},status_code=403)
        if request.headers.get('content-length') and int(request.headers['content-length'])>22*1024*1024:
            return JSONResponse({'detail':'A feltöltés legfeljebb 20 MB lehet.'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse({'detail':'Ellenőrizze a megadott adatokat.','errors':[{'field':'.'.join(map(str,e['loc'])),'message':e['msg']} for e in exc.errors()]},status_code=422)


def password_hash(password):
    salt=secrets.token_hex(16)
    result=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return salt+':'+result


def password_matches(password, encoded):
    salt,digest=encoded.split(':')
    result=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return hmac.compare_digest(result,digest)


def user(request:WebRequest):
    token=request.cookies.get('kkv_session','')
    if not token:raise HTTPException(401,'Jelentkezzen be.')
    with db.connection() as con:
        row=con.execute('SELECT u.id,u.name,u.username,u.role,u.active,s.csrf,s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=?',
                        (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row or not row['active'] or row['expires']<db.now():raise HTTPException(401,'A munkamenet lejárt. Jelentkezzen be újra.')
    if request.method not in ['GET','HEAD'] and not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),row['csrf']):
        raise HTTPException(403,'Érvénytelen kérésazonosító. Frissítse az oldalt.')
    return dict(row)


def staff(u=Depends(user)):
    if u['role']=='client':raise HTTPException(403,'Ehhez belső munkatársi jogosultság szükséges.')
    return u


def reviewer(u=Depends(staff)):
    if u['role'] not in ['admin','reviewer']:raise HTTPException(403,'Szakértői jóváhagyási jogosultság szükséges.')
    return u


def admin(u=Depends(staff)):
    if u['role']!='admin':raise HTTPException(403,'Adminisztrátori jogosultság szükséges.')
    return u


def visible_case(con,cid,u):
    row=con.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone()
    if not row or (u['role']=='client' and row['client_user_id']!=u['id']):raise HTTPException(404,'Az ügy nem található.')
    return dict(row)


def session_response(u):
    token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(24)
    with db.connection() as con:
        con.execute('DELETE FROM sessions WHERE expires<?',(db.now(),))
        con.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],csrf,(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()))
    response=JSONResponse({'user':{k:u[k] for k in ['id','name','username','role']},'csrf':csrf})
    response.set_cookie('kkv_session',token,httponly=True,samesite='strict',secure=os.environ.get('KKV_SECURE_COOKIES')=='1',max_age=43200)
    return response


class Account(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    username:str=Field(min_length=3,max_length=120,pattern=r'^[A-Za-z0-9_.@+-]+$')
    password:str=Field(min_length=12,max_length=200)
    role:str='analyst'


@app.get('/api/health')
def health():return {'status':'ok','rule_version':RULE_VERSION}


@app.get('/api/auth/status')
def auth_status():
    with db.connection() as con:
        return {'setup_required':con.execute('SELECT count(*) FROM users').fetchone()[0]==0}


@app.post('/api/auth/setup')
def setup(payload:Account):
    with db.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT count(*) FROM users').fetchone()[0]:raise HTTPException(409,'Az első fiók már létrejött.')
        uid=str(uuid4());con.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(uid,payload.name,payload.username.lower(),password_hash(payload.password),'admin',1,db.now()))
        db.audit(con,None,uid,'account_setup','Első adminisztrátor létrehozva.')
    return session_response({'id':uid,'name':payload.name,'username':payload.username.lower(),'role':'admin'})


class Login(BaseModel):
    username:str=Field(max_length=120)
    password:str=Field(max_length=200)


@app.post('/api/auth/login')
def login(payload:Login, request:WebRequest):
    key=request.client.host if request.client else 'unknown';attempts=login_attempts[key]
    while attempts and attempts[0]<time.monotonic()-300:attempts.popleft()
    if len(attempts)>=10:raise HTTPException(429,'Túl sok belépési kísérlet. Próbálja újra öt perc múlva.')
    with db.connection() as con:
        row=con.execute('SELECT * FROM users WHERE username=? AND active=1',(payload.username.lower(),)).fetchone()
    if not row or not password_matches(payload.password,row['password']):
        attempts.append(time.monotonic());raise HTTPException(401,'Hibás felhasználónév vagy jelszó.')
    attempts.clear();return session_response(dict(row))


@app.get('/api/auth/me')
def me(u=Depends(user)):return {'user':{k:u[k] for k in ['id','name','username','role']},'csrf':u['csrf']}


@app.post('/api/auth/logout')
def logout(request:WebRequest,u=Depends(user)):
    with db.connection() as con:con.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(request.cookies['kkv_session'].encode()).hexdigest(),))
    response=JSONResponse({'ok':True});response.delete_cookie('kkv_session');return response


@app.get('/api/users')
def users(u=Depends(staff)):
    with db.connection() as con:return [dict(r) for r in con.execute('SELECT id,name,username,role,active FROM users ORDER BY name')]


@app.post('/api/users')
def create_user(payload:Account,u=Depends(admin)):
    if payload.role not in ['admin','reviewer','analyst','client']:raise HTTPException(422,'Ismeretlen szerepkör.')
    uid=str(uuid4())
    with db.connection() as con:
        if con.execute('SELECT id FROM users WHERE username=?',(payload.username.lower(),)).fetchone():raise HTTPException(409,'Ez a felhasználónév már foglalt.')
        con.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(uid,payload.name,payload.username.lower(),password_hash(payload.password),payload.role,1,db.now()))
        db.audit(con,None,u['id'],'account_created',f'{payload.name}: {payload.role}')
    return {'id':uid}


class CaseInput(BaseModel):
    data:Assessment
    version:int|None=None
    client_user_id:str|None=None


def persist_new(data,u,client_user_id=None):
    cid=str(uuid4());stamp=db.now();raw=data.model_dump(mode='json');calc=calculate(data)
    with db.connection() as con:
        if client_user_id:
            assigned=con.execute('SELECT role FROM users WHERE id=? AND active=1',(client_user_id,)).fetchone()
            if not assigned or assigned['role']!='client':raise HTTPException(422,'Az ügy csak aktív ügyfélfiókhoz rendelhető.')
        con.execute('INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?)',(cid,db.dumps(raw),1,'draft',stamp,stamp,u['id'],client_user_id,None))
        # Explicit column names make snapshot evolution independent of table order.
        con.execute('INSERT INTO versions(case_id,version,data,calculation,created,author) VALUES(?,?,?,?,?,?)',(cid,1,db.dumps(raw),db.dumps(calc),stamp,u['id']))
        db.audit(con,cid,u['id'],'created',data.title)
    return {'id':cid,'version':1}


@app.get('/api/cases')
def list_cases(u=Depends(user)):
    with db.connection() as con:
        rows=con.execute('SELECT * FROM cases '+('WHERE client_user_id=? ' if u['role']=='client' else '')+'ORDER BY updated DESC', (u['id'],) if u['role']=='client' else ())
        out=[]
        for r in rows:
            data=json.loads(r['data']);calc=None
            # Clients only see the approved snapshot's result.
            v=r['approved_version'] if u['role']=='client' else r['version']
            snapshot=con.execute('SELECT data,calculation FROM versions WHERE case_id=? AND version=?',(r['id'],v)).fetchone() if v else None
            if snapshot:
                calc=json.loads(snapshot['calculation'])
                if u['role']=='client':data=json.loads(snapshot['data'])
            out.append({'id':r['id'],'title':data['title'],'client':data['client'],'years':data['years'],
                'status':'approved' if u['role']=='client' and r['approved_version'] else r['status'] if u['role']!='client' else 'intake',
                'version':v,'updated':r['updated'],'category':calc['category'] if calc else None,'label':calc['label'] if calc else 'Adatbekérés',
                'blockers':len(calc['blockers']) if calc and u['role']!='client' else 0})
        return out


@app.post('/api/cases')
def new_case(payload:CaseInput,u=Depends(staff)):return persist_new(payload.data,u,payload.client_user_id)


@app.post('/api/cases/demo')
def demo(u=Depends(staff)):return persist_new(demonstration(),u)


@app.post('/api/cases/import')
async def excel_import(file:UploadFile=File(...),u=Depends(staff)):
    if not (file.filename or '').lower().endswith('.xlsx'):raise HTTPException(422,'XLSX-fájl szükséges.')
    raw=await file.read(20*1024*1024+1)
    if len(raw)>20*1024*1024:raise HTTPException(413,'A fájl legfeljebb 20 MB lehet.')
    try:data=import_excel(raw,Path(file.filename).name)
    except Exception as e:
        if isinstance(e,ValidationError):raise HTTPException(422,'Az importált adatok hiányosak vagy hibásak. '+str(e.errors()[0]['msg']))
        raise HTTPException(422,'Az Excel nem olvasható. '+str(e)[:300])
    result=persist_new(data,u)
    store_document(result['id'],raw,file.filename,u)
    return result


@app.get('/api/template')
def template(u=Depends(staff)):
    return Response(template_bytes(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="KKV_adatbekeres.xlsx"'})


@app.get('/api/cases/{cid}')
def get_case(cid:str,u=Depends(user)):
    with db.connection() as con:
        row=visible_case(con,cid,u)
        if u['role']=='client':
            if row['approved_version']:
                snap=con.execute('SELECT data,calculation,approved_at FROM versions WHERE case_id=? AND version=?',(cid,row['approved_version'])).fetchone()
                d=json.loads(snap['data']);c=json.loads(snap['calculation'])
                return {'id':cid,'client_view':True,'title':d['title'],'purpose':d['purpose'],'years':d['years'],
                    'version':row['approved_version'],'status':'approved','label':c['label'],'approved_at':snap['approved_at'],
                    'totals':[{'year':y['year'],'totals':y['totals'],'label':y['label']} for y in c['years']]}
            d=json.loads(row['data']);return {'id':cid,'client_view':True,'title':d['title'],'purpose':d['purpose'],'years':d['years'],'status':'intake'}
        v=con.execute('SELECT calculation FROM versions WHERE case_id=? AND version=?',(cid,row['version'])).fetchone()
        return {'id':cid,'data':json.loads(row['data']),'calculation':json.loads(v['calculation']),
            'version':row['version'],'status':row['status'],'approved_version':row['approved_version'],
            'client_user_id':row['client_user_id'],'updated':row['updated']}


@app.put('/api/cases/{cid}')
def update_case(cid:str,payload:CaseInput,u=Depends(staff)):
    calc=calculate(payload.data);raw=payload.data.model_dump(mode='json');stamp=db.now()
    with db.connection() as con:
        con.execute('BEGIN IMMEDIATE');row=visible_case(con,cid,u)
        if payload.version!=row['version']:raise HTTPException(409,'Az ügyet közben más módosította. Töltse újra a legfrissebb verziót.')
        if payload.client_user_id:
            assigned=con.execute('SELECT role FROM users WHERE id=? AND active=1',(payload.client_user_id,)).fetchone()
            if not assigned or assigned['role']!='client':raise HTTPException(422,'Aktív ügyfélfiók szükséges.')
        v=row['version']+1
        con.execute('UPDATE cases SET data=?,version=?,status=?,updated=?,client_user_id=? WHERE id=?',
                    (db.dumps(raw),v,'draft',stamp,payload.client_user_id,cid))
        con.execute('INSERT INTO versions(case_id,version,data,calculation,created,author) VALUES(?,?,?,?,?,?)',(cid,v,db.dumps(raw),db.dumps(calc),stamp,u['id']))
        db.audit(con,cid,u['id'],'saved',f'{v}. verzió; korábbi jóváhagyás változatlan pillanatképben megőrizve.')
    return {'version':v,'calculation':calc,'status':'draft'}


@app.get('/api/cases/{cid}/calculate')
def recalculate(cid:str,scenario:str='base',u=Depends(staff)):
    if scenario not in ['base','all']:raise HTTPException(422,'Ismeretlen forgatókönyv.')
    with db.connection() as con:row=visible_case(con,cid,u)
    return calculate(Assessment.model_validate_json(row['data']),scenario)


class Approval(BaseModel):
    version:int
    financials:bool
    relationships:bool
    rules:bool
    note:str=Field(default='',max_length=3000)


@app.post('/api/cases/{cid}/approve')
def approve(cid:str,payload:Approval,u=Depends(reviewer)):
    if not all([payload.financials,payload.relationships,payload.rules]):raise HTTPException(422,'Mindhárom szakértői ellenőrzés szükséges.')
    with db.connection() as con:
        con.execute('BEGIN IMMEDIATE');row=visible_case(con,cid,u)
        if row['version']!=payload.version:raise HTTPException(409,'Az ügy verziója megváltozott.')
        if row['status']=='approved':raise HTTPException(409,'Ez a verzió már jóváhagyott.')
        calc=calculate(Assessment.model_validate_json(row['data']))
        if not calc['ready']:raise HTTPException(422,{'message':'A tisztázandó kérdések miatt az ügy nem véglegesíthető.','blockers':calc['blockers']})
        pending=con.execute('SELECT count(*) FROM intake WHERE case_id=? AND reviewed=0',(cid,)).fetchone()[0]
        if pending:raise HTTPException(422,'Feldolgozatlan ügyfélválaszok vannak. Előbb ellenőrizze ezeket.')
        stamp=db.now()
        con.execute('UPDATE versions SET approved_at=?,approver=?,confirmations=?,calculation=? WHERE case_id=? AND version=?',
            (stamp,u['id'],db.dumps(payload.model_dump()),db.dumps(calc),cid,row['version']))
        con.execute('UPDATE cases SET status=?,approved_version=?,updated=? WHERE id=?',('approved',row['version'],stamp,cid))
        db.audit(con,cid,u['id'],'approved',f"{row['version']}. verzió. {payload.note}")
    return {'status':'approved','version':payload.version}


@app.get('/api/cases/{cid}/audit')
def case_audit(cid:str,u=Depends(staff)):
    with db.connection() as con:
        visible_case(con,cid,u)
        return [dict(r) for r in con.execute('SELECT a.id,a.action,a.details,a.created,u.name AS actor FROM audit a LEFT JOIN users u ON u.id=a.actor WHERE case_id=? ORDER BY a.id DESC',(cid,))]


@app.get('/api/cases/{cid}/versions')
def versions(cid:str,u=Depends(staff)):
    with db.connection() as con:
        visible_case(con,cid,u)
        return [dict(r) for r in con.execute('SELECT v.version,v.created,v.approved_at,u.name AS author FROM versions v JOIN users u ON u.id=v.author WHERE case_id=? ORDER BY version DESC',(cid,))]


@app.get('/api/cases/{cid}/versions/{version}')
def version(cid:str,version:int,u=Depends(staff)):
    with db.connection() as con:
        visible_case(con,cid,u)
        r=con.execute('SELECT data,calculation,approved_at FROM versions WHERE case_id=? AND version=?',(cid,version)).fetchone()
        if not r:raise HTTPException(404,'A verzió nem található.')
        return {'data':json.loads(r['data']),'calculation':json.loads(r['calculation']),'approved_at':r['approved_at'],'version':version}


ALLOWED_FILES={'.pdf','.docx','.xlsx','.png','.jpg','.jpeg','.txt'}


def store_document(cid,raw,filename,u):
    filename=Path((filename or 'dokumentum').replace('\\','/')).name[:200]
    ext=Path(filename).suffix.lower()
    if ext not in ALLOWED_FILES:raise HTTPException(422,'PDF, DOCX, XLSX, PNG, JPG vagy TXT tölthető fel.')
    did=str(uuid4());stored=did+ext;folder=db.data_dir()/'uploads';folder.mkdir(exist_ok=True)
    with db.connection() as con:
        visible_case(con,cid,u)
        (folder/stored).write_bytes(raw)
        con.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',(did,cid,filename,stored,len(raw),hashlib.sha256(raw).hexdigest(),u['id'],db.now()))
        db.audit(con,cid,u['id'],'document_uploaded',filename)
    return {'id':did,'filename':filename}


@app.get('/api/cases/{cid}/documents')
def documents(cid:str,u=Depends(user)):
    with db.connection() as con:
        visible_case(con,cid,u)
        return [dict(r) for r in con.execute('SELECT id,filename,size,sha256,created,author FROM documents WHERE case_id=?'+(' AND author=?' if u['role']=='client' else '')+' ORDER BY created DESC',(cid,u['id']) if u['role']=='client' else (cid,))]


@app.post('/api/cases/{cid}/documents')
async def upload_document(cid:str,file:UploadFile=File(...),u=Depends(user)):
    raw=await file.read(20*1024*1024+1)
    if len(raw)>20*1024*1024:raise HTTPException(413,'A fájl legfeljebb 20 MB lehet.')
    if not raw:raise HTTPException(422,'Üres fájl nem tölthető fel.')
    return store_document(cid,raw,file.filename,u)


@app.get('/api/cases/{cid}/documents/{did}')
def download_document(cid:str,did:str,u=Depends(user)):
    with db.connection() as con:
        visible_case(con,cid,u)
        row=con.execute('SELECT * FROM documents WHERE id=? AND case_id=?',(did,cid)).fetchone()
        if not row or (u['role']=='client' and row['author']!=u['id']):raise HTTPException(404,'A dokumentum nem található.')
    return FileResponse(db.data_dir()/'uploads'/row['stored_name'],filename=row['filename'],media_type='application/octet-stream')


class Intake(BaseModel):
    message:str=Field(min_length=5,max_length=20000)


@app.post('/api/cases/{cid}/intake')
def submit_intake(cid:str,payload:Intake,u=Depends(user)):
    with db.connection() as con:
        visible_case(con,cid,u);iid=str(uuid4())
        con.execute('INSERT INTO intake VALUES(?,?,?,?,?,?)',(iid,cid,u['id'],payload.message,db.now(),0))
        db.audit(con,cid,u['id'],'intake_received','Új adatbekérési válasz.')
    return {'id':iid}


@app.get('/api/cases/{cid}/intake')
def intake(cid:str,u=Depends(user)):
    with db.connection() as con:
        visible_case(con,cid,u)
        return [dict(r) for r in con.execute('SELECT i.id,i.message,i.created,i.reviewed,u.name AS author FROM intake i JOIN users u ON u.id=i.author WHERE case_id=?'+(' AND i.author=?' if u['role']=='client' else '')+' ORDER BY i.created DESC',(cid,u['id']) if u['role']=='client' else (cid,))]


@app.post('/api/cases/{cid}/intake/{iid}/review')
def review_intake(cid:str,iid:str,u=Depends(staff)):
    with db.connection() as con:
        visible_case(con,cid,u)
        result=con.execute('UPDATE intake SET reviewed=1 WHERE id=? AND case_id=?',(iid,cid))
        if not result.rowcount:raise HTTPException(404,'A válasz nem található.')
        db.audit(con,cid,u['id'],'intake_reviewed','Ügyfélválasz feldolgozva.')
    return {'ok':True}


@app.get('/api/cases/{cid}/report/{kind}')
def report(cid:str,kind:str,version:int|None=None,u=Depends(user)):
    if kind not in ['docx','pdf']:raise HTTPException(404,'Ismeretlen exportformátum.')
    with db.connection() as con:
        case=visible_case(con,cid,u)
        v=version or (case['approved_version'] if u['role']=='client' else case['version'])
        row=con.execute('SELECT v.*,u.name AS approver_name FROM versions v LEFT JOIN users u ON u.id=v.approver WHERE case_id=? AND version=?',(cid,v)).fetchone()
        if not row or (u['role']=='client' and not row['approved_at']):raise HTTPException(404,'Jóváhagyott dokumentum még nem érhető el.')
        data=Assessment.model_validate_json(row['data']);calc=json.loads(row['calculation'])
        meta={'id':cid,'version':v,'approved':bool(row['approved_at']),'approved_at':row['approved_at'],'approver':row['approver_name']}
    exports=db.data_dir()/'exports';exports.mkdir(exist_ok=True)
    stem=f'{cid}-v{v}-'+('approved' if meta['approved'] else 'draft')
    docpath=exports/(stem+'.docx')
    if not docpath.exists():
        raw=word_report(data,calc,meta)
        with tempfile.NamedTemporaryFile(dir=exports,delete=False) as f:
            f.write(raw);tmp=Path(f.name)
        os.replace(tmp,docpath)
    path=docpath
    if kind=='pdf':
        path=exports/(stem+'.pdf')
        if not path.exists():
            try:
                with tempfile.TemporaryDirectory(dir=exports) as folder:
                    subprocess.run(['soffice',f'-env:UserInstallation={Path(folder).as_uri()}/profile','--headless','--convert-to','pdf','--outdir',folder,str(docpath)],
                        check=True,timeout=60,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    pdf=Path(folder)/(stem+'.pdf')
                    if not pdf.exists():raise RuntimeError('Nem keletkezett PDF.')
                    os.replace(pdf,path)
            except (OSError,subprocess.SubprocessError,RuntimeError):
                raise HTTPException(503,'A PDF-konverzió nem sikerült. A Word-export elérhető; ellenőrizze a LibreOffice telepítését.')
    with db.connection() as con:db.audit(con,cid,u['id'],'report_downloaded',f'{v}. verzió, {kind}')
    return FileResponse(path,filename=f'KKV_allasfoglalas_v{v}.{kind}',media_type='application/pdf' if kind=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')


@app.get('/api/mnb')
def mnb(day:date,u=Depends(staff)):
    if day>date.today():raise HTTPException(422,'Jövőbeli árfolyam nem kérhető le.')
    start=day-timedelta(days=10)
    xml=f'''<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><GetExchangeRates xmlns="http://www.mnb.hu/webservices/"><startDate>{start}</startDate><endDate>{day}</endDate><currencyNames>EUR</currencyNames></GetExchangeRates></soap:Body></soap:Envelope>'''
    try:
        req=Request('https://www.mnb.hu/arfolyamok.asmx',data=xml.encode(),headers={'Content-Type':'text/xml; charset=utf-8','SOAPAction':'http://www.mnb.hu/webservices/GetExchangeRates'})
        with urlopen(req,timeout=8) as response:raw=response.read(2*1024*1024)
        root=ET.fromstring(raw)
        result=next(n.text for n in root.iter() if n.tag.endswith('GetExchangeRatesResult'))
        parsed=ET.fromstring(result)
        days=sorted(parsed.findall('.//Day'),key=lambda n:n.attrib['date'])
        candidates=[n for n in days if n.attrib['date']<=day.isoformat()]
        latest=candidates[-1]
        rate=next(n for n in latest.findall('Rate') if n.attrib.get('curr')=='EUR')
        value=Decimal(rate.text.replace(',','.'))/Decimal(rate.attrib.get('unit','1'))
        return {'date':day.isoformat(),'quoted':latest.attrib['date'],'value':str(value),'confirmed':True,'source':'https://www.mnb.hu/arfolyamok.asmx – hivatalos MNB-lekérés'}
    except Exception:
        raise HTTPException(502,'Az MNB-forrás jelenleg nem érhető el. Rögzítse az árfolyamot és a hivatalos forrást kézzel, majd jelölje az ellenőrzést.')


from .tao_api import build_router as tao_router

app.include_router(tao_router(user, staff, reviewer))
from .pdf_api import build_router as pdf_router
app.include_router(pdf_router(staff))
app.mount('/static',StaticFiles(directory=STATIC),name='static')


@app.get('/')
def index():return FileResponse(STATIC/'index.html')
