"""Quarantined multi-PDF upload, editable candidates, separately created draft cases."""
import hashlib
import json
import shutil
from datetime import date, timedelta
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from typing import Literal
from uuid import uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import Field, ValidationError

from . import db, tao_db
from .engine import calculate as kkv_calculate
from .models import Assessment, Model
from .pdf_import import PARSER_VERSION, entity_id, extract
from .tao_api import snapshot, advance, validate_documents
from .pdf_merge import proposals, merge
from .tao_models import TaoAssessment, VotingFact


class Review(Model):
    module: Literal['tao', 'kkv']
    title: str = Field(min_length=1, max_length=200)
    as_of: date
    years: list[int] = Field(default_factory=list, max_length=10)
    root: str = Field(default='', max_length=80)
    documents: list[dict] = Field(min_length=1, max_length=20)
    confirmed: bool = False
    note: str = Field(default='', max_length=3000)


class MergeReview(Review):
    target_case_id: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1)
    entity_matches: dict[str, str] = Field(default_factory=dict, max_length=500)
    token: str = Field(default='', max_length=64)
    selected: list[str] = Field(default_factory=list, max_length=5000)


def initialize():
    with db.connection() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS pdf_batches(
          id TEXT PRIMARY KEY, author TEXT NOT NULL REFERENCES users(id), created TEXT NOT NULL,
          files TEXT NOT NULL, parser_version TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pdf_applications(
          batch_id TEXT NOT NULL REFERENCES pdf_batches(id), module TEXT NOT NULL,
          case_id TEXT NOT NULL, review TEXT NOT NULL, created TEXT NOT NULL,
          PRIMARY KEY(batch_id,module));
        ''')


def draft(payload, partial=False):
    """Build an unapproved case. Unknown percentages never become zero ownerships."""
    companies, persons, facts, financials, notes = {}, {}, [], {}, []
    names = {}
    for doc in payload.documents:
        cid = entity_id(doc.get('registration', ''), doc.get('name', ''))
        companies.setdefault(cid, dict(id=cid, name=doc.get('name', ''), registration=doc.get('registration', '')))
        for alias in [doc.get('name', ''), *doc.get('aliases', [])]:
            names[alias.casefold()] = cid
    for doc in payload.documents:
        target = entity_id(doc.get('registration', ''), doc.get('name', ''))
        for owner in doc.get('owners', []):
            name = owner.get('name', '')
            if not name:
                raise ValueError('A tulajdonos neve nem maradhat üres.')
            corporate = bool(owner.get('registration')) or any(s in name for s in ['Kft.', 'Zrt.', 'Társaság', 'Részvénytársaság', 'Holding'])
            oid = entity_id(owner.get('registration', ''), name)
            if not owner.get('registration') and name.casefold() in names:
                oid = names[name.casefold()]
            elif corporate:
                companies.setdefault(oid, dict(id=oid, name=name, registration=owner.get('registration', '')))
            else:
                # Name alone is a candidate identity; verification is mandatory, never a kinship proof.
                persons.setdefault(oid, dict(id=oid, name=name, notes='PDF-ből javasolt személy; azonosság szakértőileg ellenőrzendő.'))
            fact = dict(id=str(uuid4()), owner=oid, company=target, capital=owner.get('capital'),
                        capacity='trustee' if owner.get('trustee') else 'own', vote_mode=owner.get('vote_mode', 'unknown'), votes=owner.get('votes'), vote_bound=owner.get('vote_bound', 'exact'),
                        valid_from=owner.get('valid_from'), valid_to=owner.get('valid_to'), registered_on=owner.get('registered_on'),
                        deletion_registered_on=owner.get('deletion_registered_on'), evidence={**owner.get('evidence', {}), 'document_id':doc.get('document_id')},
                        reason=owner.get('reason', ''))
            VotingFact.model_validate(fact)
            facts.append(fact)
            notes.append(f"{name} → {doc['name']}: {json.dumps(owner, ensure_ascii=False)}")
        for leader in doc.get('leaders', []):
            notes.append(f"Vezetőjelölt – {doc['name']}: {json.dumps(leader, ensure_ascii=False)}")
        for row in doc.get('financials', []):
            if row['year'] not in payload.years:
                continue
            if payload.module == 'kkv' and (row.get('turnover') is not None or row.get('balance') is not None) and not all([row.get('start'), row.get('end')]):
                raise ValueError(f"{doc['name']} · {row['year']}: a beszámolási időszak kezdete és vége ellenőrizendő.")
            key = (target, row['year'])
            value = dict(company=target, year=row['year'], employees=row.get('employees'),
                         turnover=None if row.get('turnover') is None else str(Decimal(str(row['turnover'])) * 1000),
                         balance=None if row.get('balance') is None else str(Decimal(str(row['balance'])) * 1000),
                         start=row.get('start'), end=row.get('end'), currency='HUF', employment_method='estimate' if row.get('employees') is not None else 'annual', source=f"{doc['source']} · {row['evidence']['page']}. oldal; ezer HUF → HUF ×1000")
            if key in financials and financials[key] != value:
                # Same data may have a different source; contradictions must never be silently replaced.
                for field in ['employees', 'turnover', 'balance']:
                    if financials[key][field] != value[field]:
                        raise ValueError(f"Eltérő {row['year']}. évi {field}: {doc['name']}. Az egyik forrás pénzügyi sorát távolítsa el az ellenőrzésnél.")
            else:
                financials[key] = value
    common = dict(title=payload.title, as_of=payload.as_of, companies=list(companies.values()), persons=list(persons.values()))
    if payload.module == 'tao':
        raw = dict(**{**common, 'as_of':payload.as_of.isoformat()}, voting_facts=[VotingFact.model_validate(f).model_dump(mode='json') for f in facts],
            assumptions='PDF-importból készült tervezet. Személyazonosság, rokonság, irányítás, BVK és közvetett befolyás szakértői ellenőrzést igényel. ' + payload.note)
        data = raw if partial else TaoAssessment(**raw)
    else:
        if payload.root not in companies:
            payload.root = entity_id(payload.root, '')
        if not payload.years or payload.root not in companies:
            raise ValueError('KKV-vizsgálathoz válasszon céget és legalább egy évet.')
        ownerships = []
        seen_ownerships = set()
        for fact in facts:
            if fact['capacity'] != 'own' or fact['capital'] is None or fact['vote_bound'] != 'exact' or fact['vote_mode'] == 'unknown' or not fact['valid_from']:
                continue
            votes = fact['capital'] if fact['vote_mode'] == 'ownership_default' else fact['votes']
            if votes is None:
                continue
            signature = tuple(str(fact[k]) for k in ['owner','company','capital','votes','vote_mode','valid_from','valid_to'])
            if signature in seen_ownerships:
                continue
            seen_ownerships.add(signature)
            ownerships.append(dict(id=fact['id'], owner=fact['owner'], company=fact['company'], capital=fact['capital'], votes=votes,
                start=fact['valid_from'], end=(date.fromisoformat(fact['valid_to']) - timedelta(days=1)).isoformat() if fact['valid_to'] else None, source=fact['evidence'].get('source', ''),
                reason='Ellenőrzött PDF-jelölt; tulajdon = szavazat feltételezés.' if fact['vote_mode']=='ownership_default' else fact['reason']))
        decisions = [dict(id=str(uuid4()), first=a, second=b, relation='unresolved', basis='expert',
            reason='PDF-import: külön KKV-kapcsolati minősítés szükséges.', source='OPTEN PDF-import', confirmed=False)
            for a,b in combinations(companies, 2)]
        data = Assessment(**common, root=payload.root, years=sorted(set(payload.years)), ownerships=ownerships,
                          decisions=decisions, financials=list(financials.values()),
                          assumptions='PDF-import; a létszám éves módszertana és a jogi kapcsolatok ellenőrzendők. ' + payload.note)
    return data, notes


def build_router(staff):
    router = APIRouter()
    def batch(con, bid, uid):
        row = con.execute('SELECT * FROM pdf_batches WHERE id=? AND author=?', (bid, uid)).fetchone()
        if not row:
            raise HTTPException(404, 'Az import nem található.')
        return dict(row)

    @router.get('/pdf-import')
    def page():
        return FileResponse(Path(__file__).parent / 'static' / 'pdf-import.html')

    @router.post('/api/pdf/batches')
    def upload(files: list[UploadFile] = File(...), u=Depends(staff)):
        if not 1 <= len(files) <= 20:
            raise HTTPException(422, 'Egyszerre 1–20 PDF tölthető fel, összesen legfeljebb 20 MB méretben.')
        bid = str(uuid4()); folder = db.data_dir() / 'pdf-batches' / bid
        folder.mkdir(parents=True)
        results, size = [], 0
        try:
            for file in files:
                name = Path((file.filename or '').replace('\\', '/')).name[:200]
                if not name.lower().endswith('.pdf'):
                    raise HTTPException(422, 'Csak PDF-fájl tölthető fel.')
                raw = file.file.read(20*1024*1024+1); size += len(raw)
                if size > 20*1024*1024:
                    raise HTTPException(413, 'Az összes PDF együtt legfeljebb 20 MB lehet.')
                did = str(uuid4()); path = folder / (did + '.pdf'); path.write_bytes(raw)
                try:
                    candidate = extract(path, name)
                    error = None
                except ValueError as exc:
                    candidate = None; error = str(exc)
                except RuntimeError as exc:
                    raise HTTPException(503, str(exc))
                results.append(dict(id=did, filename=name, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw),
                                    candidate=candidate, error=error))
            with db.connection() as con:
                con.execute('INSERT INTO pdf_batches VALUES(?,?,?,?,?)', (bid, u['id'], db.now(), db.dumps(results), PARSER_VERSION))
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return dict(id=bid, files=results, parser_version=PARSER_VERSION)

    @router.get('/api/pdf/batches/{bid}')
    def get_batch(bid: str, u=Depends(staff)):
        with db.connection() as con:
            row = batch(con, bid, u['id'])
            return dict(id=bid, files=json.loads(row['files']), parser_version=row['parser_version'])

    @router.get('/api/pdf/batches/{bid}/files/{did}')
    def file_source(bid: str, did: str, u=Depends(staff)):
        with db.connection() as con:
            row = batch(con, bid, u['id'])
            source = next((f for f in json.loads(row['files']) if f['id'] == did), None)
            if not source:
                raise HTTPException(404, 'A forrás nem található.')
        return FileResponse(db.data_dir() / 'pdf-batches' / bid / (did+'.pdf'), filename=source['filename'], media_type='application/pdf')

    def prepare_merge(con, bid, payload, uid):
        row = batch(con, bid, uid)
        if con.execute('SELECT 1 FROM pdf_applications WHERE batch_id=? AND module=?', (bid,payload.module)).fetchone():
            raise HTTPException(409, 'Ez a PDF-csomag ebben a vizsgálattípusban már felhasználásra került.')
        valid = {f['id']:f for f in json.loads(row['files']) if f['candidate']}
        ids = [d.get('document_id') for d in payload.documents]
        if len(ids)!=len(set(ids)) or any(did not in valid for did in ids):
            raise HTTPException(422, 'Idegen vagy ismételt PDF-forrás az összehasonlításban.')
        table = 'tao_cases' if payload.module=='tao' else 'cases'
        case = con.execute(f'SELECT * FROM {table} WHERE id=?',(payload.target_case_id,)).fetchone()
        if not case:raise HTTPException(404, 'A célvizsgálat nem található.')
        case = dict(case)
        if case['version'] != payload.version:raise HTTPException(409, 'Az ügy közben változott. Készítsen új összehasonlítást a friss verzióval.')
        temporary=payload.model_copy(deep=True)
        if payload.module=='kkv':temporary.root=entity_id(payload.documents[0].get('registration',''),payload.documents[0].get('name',''))
        incoming,notes=draft(temporary,partial=True)
        incoming=incoming.model_dump(mode='json') if hasattr(incoming,'model_dump') else incoming
        for coll in ('voting_facts','ownerships','decisions'):
            for i,fact in enumerate(incoming.get(coll,[])):
                fact['id']=str(uuid5(NAMESPACE_URL,bid+':'+coll+':'+str(i)))
        existing=json.loads(case['data'])
        comparison=proposals(existing,incoming,payload.module,bid+':'+case['id'],payload.entity_matches)
        return case,existing,valid,ids,notes,comparison

    @router.post('/api/pdf/batches/{bid}/compare')
    def compare(bid: str, payload: MergeReview, u=Depends(staff)):
        if len(db.dumps(payload.documents)) > 2*1024*1024:raise HTTPException(413,'Túl nagy ellenőrzési adatcsomag.')
        try:
            with db.connection() as con:
                case,_,_,_,_,comparison=prepare_merge(con,bid,payload,u['id'])
            return dict(**comparison,version=case['version'],case_id=case['id'])
        except (ValueError, KeyError, TypeError, ArithmeticError, AttributeError, IndexError) as exc:
            raise HTTPException(422,'Az összehasonlítás adatai ellenőrizendők: '+str(exc)[:500])

    @router.post('/api/pdf/batches/{bid}/merge')
    def merge_into_case(bid: str, payload: MergeReview, u=Depends(staff)):
        if not payload.confirmed or not payload.token:raise HTTPException(422,'Az összehasonlítás és a források külön jóváhagyása szükséges.')
        if len(db.dumps(payload.documents)) > 2*1024*1024:raise HTTPException(413,'Túl nagy ellenőrzési adatcsomag.')
        copied=[]
        try:
            with db.connection() as con:
                con.execute('BEGIN IMMEDIATE')
                case,existing,valid,ids,notes,comparison=prepare_merge(con,bid,payload,u['id'])
                if comparison['token'] != payload.token:raise HTTPException(409,'Az adatok vagy az azonossági döntések változtak. Készítsen új összehasonlítást.')
                data=merge(existing,comparison,payload.selected,payload.module)
                cid=case['id'];stamp=db.now()
                folder=db.data_dir()/'uploads'/('tao' if payload.module=='tao' else '')
                folder.mkdir(parents=True,exist_ok=True)
                for did in ids:
                    f=valid[did];dest=folder/(did+'.pdf')
                    if dest.exists():raise HTTPException(409,'A forrásfájl már szerepel az adattárban.')
                    shutil.copyfile(db.data_dir()/'pdf-batches'/bid/(did+'.pdf'),dest);copied.append(dest)
                    if payload.module=='tao':
                        con.execute('INSERT INTO tao_documents VALUES(?,?,?,?,?,?,?,?,?,?)',(did,cid,f['filename'],did+'.pdf',f['size'],f['sha256'],u['id'],stamp,stamp,u['id']))
                    else:
                        con.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',(did,cid,f['filename'],did+'.pdf',f['size'],f['sha256'],u['id'],stamp))
                if payload.module=='tao':
                    validate_documents(con,cid,data)
                    version,_=advance(con,case,data,u['id'])
                    tao_db.audit(con,cid,u['id'],'pdf_merged',f'{bid}; {len(payload.selected)} kijelölt adatcsoport; új szakértői ellenőrzés szükséges.')
                else:
                    version=case['version']+1;raw=data.model_dump(mode='json')
                    con.execute('UPDATE cases SET data=?,version=?,status=?,updated=? WHERE id=?',(db.dumps(raw),version,'draft',stamp,cid))
                    con.execute('INSERT INTO versions(case_id,version,data,calculation,created,author) VALUES(?,?,?,?,?,?)',(cid,version,db.dumps(raw),db.dumps(kkv_calculate(data)),stamp,u['id']))
                    db.audit(con,cid,u['id'],'pdf_merged',f'{bid}; {len(payload.selected)} kijelölt adatcsoport; előző jóváhagyás megőrizve.')
                    if notes:
                        con.execute('INSERT INTO intake VALUES(?,?,?,?,?,?)',(str(uuid4()),cid,u['id'],'PDF-frissítés: a forrásjelöltek és jogi kapcsolatok újraellenőrzendők.\n'+'\n'.join(notes),stamp,0))
                con.execute('INSERT INTO pdf_applications VALUES(?,?,?,?,?)',(bid,payload.module,cid,db.dumps(payload.model_dump(mode='json')),stamp))
            return dict(id=cid,version=version,module=payload.module)
        except Exception as exc:
            for dest in copied:dest.unlink(missing_ok=True)
            if isinstance(exc,(ValueError,KeyError,TypeError,ArithmeticError,AttributeError,IndexError)):
                raise HTTPException(422,'A kijelölt adatok együtt nem alkalmazhatók: '+str(exc)[:500])
            raise

    @router.post('/api/pdf/batches/{bid}/apply')
    def apply(bid: str, payload: Review, u=Depends(staff)):
        if not payload.confirmed:
            raise HTTPException(422, 'A kiolvasott adatok ellenőrzését külön meg kell erősíteni.')
        if len(db.dumps(payload.documents)) > 2*1024*1024:
            raise HTTPException(413, 'Túl nagy ellenőrzési adatcsomag.')
        try:
            data, notes = draft(payload)
        except (ValueError, ValidationError, KeyError, TypeError, ArithmeticError, AttributeError, IndexError) as exc:
            raise HTTPException(422, 'Ellenőrizze a jelölteket: ' + str(exc)[:500])
        cid = str(uuid4()); stamp = db.now(); copied = []
        try:
            with db.connection() as con:
                con.execute('BEGIN IMMEDIATE'); row = batch(con, bid, u['id'])
                if con.execute('SELECT 1 FROM pdf_applications WHERE batch_id=? AND module=?', (bid, payload.module)).fetchone():
                    raise HTTPException(409, 'Ebből az importból ez a vizsgálat már létrejött.')
                files = json.loads(row['files']); valid = {f['id']: f for f in files if f['candidate']}
                ids = [d.get('document_id') for d in payload.documents]
                if len(ids) != len(set(ids)) or any(did not in valid for did in ids):
                    raise HTTPException(422, 'Csak ehhez az importhoz tartozó, kiolvasott forrás alkalmazható.')
                table = 'tao_cases' if payload.module == 'tao' else 'cases'
                raw = data.model_dump(mode='json')
                con.execute(f'INSERT INTO {table} VALUES(?,?,?,?,?,?,?,?,?)', (cid, db.dumps(raw), 1, 'draft', stamp, stamp, u['id'], None, None))
                if payload.module == 'tao':
                    snapshot(con, cid, 1, data, u['id'])
                    tao_db.audit(con, cid, u['id'], 'pdf_reviewed', f'{bid}; {len(ids)} PDF; adatellenőrzés, külön jogi jóváhagyás még szükséges.')
                else:
                    con.execute('INSERT INTO versions(case_id,version,data,calculation,created,author) VALUES(?,?,?,?,?,?)',
                                (cid, 1, db.dumps(raw), db.dumps(kkv_calculate(data)), stamp, u['id']))
                    db.audit(con, cid, u['id'], 'pdf_reviewed', f'{bid}; adatellenőrzés, külön KKV-jóváhagyás még szükséges.')
                folder = db.data_dir() / 'uploads' / ('tao' if payload.module == 'tao' else '')
                folder.mkdir(parents=True, exist_ok=True)
                for did in ids:
                    f = valid[did]; dest = folder / (did+'.pdf')
                    shutil.copyfile(db.data_dir()/'pdf-batches'/bid/(did+'.pdf'), dest); copied.append(dest)
                    if payload.module == 'tao':
                        con.execute('INSERT INTO tao_documents VALUES(?,?,?,?,?,?,?,?,?,?)', (did,cid,f['filename'],did+'.pdf',f['size'],f['sha256'],u['id'],stamp,stamp,u['id']))
                    else:
                        con.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)', (did,cid,f['filename'],did+'.pdf',f['size'],f['sha256'],u['id'],stamp))
                if payload.module == 'kkv' and notes:
                    message = 'PDF-forrásjelöltek: az ismeretlen arányok és vezetői/azonossági kérdések rendezése szükséges.\n' + '\n'.join(notes)
                    con.execute('INSERT INTO intake VALUES(?,?,?,?,?,?)', (str(uuid4()),cid,u['id'],message,stamp,0))
                con.execute('INSERT INTO pdf_applications VALUES(?,?,?,?,?)', (bid,payload.module,cid,db.dumps(payload.model_dump(mode='json')),stamp))
        except Exception:
            for dest in copied:
                dest.unlink(missing_ok=True)
            raise
        return dict(id=cid, version=1, module=payload.module)
    return router
