import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import Field

from .tool_paths import configured_tool
from . import db, tao_db
from .models import Model
from .tao_engine import calculate
from .tao_models import TaoAssessment
from .tao_reports import word_report, xlsx_report


class CaseInput(Model):
    data: TaoAssessment
    version: int | None = Field(default=None, ge=1)
    client_user_id: str | None = None


class Approval(Model):
    version: int = Field(ge=1)
    relationships: bool
    rules: bool
    scope: bool
    partial: bool = False
    note: str = Field(default='', max_length=3000)


def visible(con, cid, u):
    row = con.execute('SELECT * FROM tao_cases WHERE id=?', (cid,)).fetchone()
    if not row or (u['role'] == 'client' and row['client_user_id'] != u['id']):
        raise HTTPException(404, 'A Tao-vizsgálat nem található.')
    return dict(row)


def validate_assignment(con, uid):
    if uid:
        row = con.execute('SELECT role FROM users WHERE id=? AND active=1', (uid,)).fetchone()
        if not row or row['role'] != 'client':
            raise HTTPException(422, 'Aktív ügyfélfiók szükséges.')


def validate_documents(con, cid, data):
    for evidence in [*[f.evidence for f in data.voting_facts], *[f.evidence for f in data.family_facts], *[d.evidence for d in data.decisions]]:
        if evidence.document_id and not con.execute('SELECT id FROM tao_documents WHERE id=? AND case_id=?', (evidence.document_id, cid)).fetchone():
            raise HTTPException(422, 'A bizonyíték dokumentuma nem ehhez a Tao-vizsgálathoz tartozik.')


def snapshot(con, cid, version, data, uid):
    raw = data.model_dump(mode='json')
    calc = calculate(data)
    con.execute('INSERT INTO tao_versions(case_id,version,data,calculation,created,author) VALUES(?,?,?,?,?,?)',
                (cid, version, db.dumps(raw), db.dumps(calc), db.now(), uid))
    return raw, calc


def advance(con, case, data, uid):
    version = case['version'] + 1
    raw, calc = snapshot(con, case['id'], version, data, uid)
    con.execute('UPDATE tao_cases SET data=?,version=?,status=?,updated=? WHERE id=?',
                (db.dumps(raw), version, 'draft', db.now(), case['id']))
    return version, calc


def build_router(user, staff, reviewer):
    router = APIRouter()

    @router.get('/api/tao/cases')
    def cases(u=Depends(user)):
        with db.connection() as con:
            rows = con.execute('SELECT * FROM tao_cases ' + ('WHERE client_user_id=? ' if u['role'] == 'client' else '') + 'ORDER BY updated DESC',
                               (u['id'],) if u['role'] == 'client' else ())
            result = []
            for case in rows:
                version = case['approved_version'] if u['role'] == 'client' else case['version']
                snap = con.execute('SELECT * FROM tao_versions WHERE case_id=? AND version=?', (case['id'], version)).fetchone() if version else None
                data = json.loads(snap['data'] if snap else case['data'])
                calc = json.loads(snap['calculation']) if snap else None
                result.append({'id': case['id'], 'title': data['title'], 'client': data['client'], 'as_of': data['as_of'],
                               'version': version, 'updated': case['updated'], 'counts': calc['counts'] if calc else None,
                               'status': ('approved_complete' if calc['complete'] else 'approved_partial') if u['role'] == 'client' and snap else case['status'] if u['role'] != 'client' else 'intake'})
            return result

    @router.post('/api/tao/cases')
    def create(payload: CaseInput, u=Depends(staff)):
        cid = str(uuid4())
        stamp = db.now()
        raw = payload.data.model_dump(mode='json')
        with db.connection() as con:
            validate_assignment(con, payload.client_user_id)
            validate_documents(con, cid, payload.data)
            con.execute('INSERT INTO tao_cases VALUES(?,?,?,?,?,?,?,?,?)',
                        (cid, db.dumps(raw), 1, 'draft', stamp, stamp, u['id'], payload.client_user_id, None))
            snapshot(con, cid, 1, payload.data, u['id'])
            tao_db.audit(con, cid, u['id'], 'created', payload.data.title)
        return {'id': cid, 'version': 1}

    @router.get('/api/tao/cases/{cid}')
    def get_case(cid: str, u=Depends(user)):
        with db.connection() as con:
            case = visible(con, cid, u)
            version = case['approved_version'] if u['role'] == 'client' else case['version']
            snap = con.execute('SELECT * FROM tao_versions WHERE case_id=? AND version=?', (cid, version)).fetchone() if version else None
            if u['role'] == 'client':
                d = json.loads(snap['data'] if snap else case['data'])
                return {'id': cid, 'client_view': True, 'title': d['title'], 'as_of': d['as_of'], 'version': version,
                        'status': 'approved' if snap else 'intake', 'counts': json.loads(snap['calculation'])['counts'] if snap else None}
            return {'id': cid, 'data': json.loads(case['data']), 'calculation': json.loads(snap['calculation']),
                    'version': version, 'status': case['status'], 'approved_version': case['approved_version'],
                    'client_user_id': case['client_user_id']}

    @router.put('/api/tao/cases/{cid}')
    def update(cid: str, payload: CaseInput, u=Depends(staff)):
        with db.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            case = visible(con, cid, u)
            if payload.version != case['version']:
                raise HTTPException(409, 'A Tao-vizsgálatot közben módosították. Töltse újra a legfrissebb verziót.')
            validate_assignment(con, payload.client_user_id)
            validate_documents(con, cid, payload.data)
            version, calc = advance(con, case, payload.data, u['id'])
            con.execute('UPDATE tao_cases SET client_user_id=? WHERE id=?', (payload.client_user_id, cid))
            tao_db.audit(con, cid, u['id'], 'saved', f'{version}. verzió; a korábbi jóváhagyás változatlan.')
        return {'version': version, 'status': 'draft', 'calculation': calc}

    @router.get('/api/tao/cases/{cid}/versions')
    def versions(cid: str, u=Depends(staff)):
        with db.connection() as con:
            visible(con, cid, u)
            return [dict(r) for r in con.execute('SELECT version,created,approved_at FROM tao_versions WHERE case_id=? ORDER BY version DESC', (cid,))]

    @router.get('/api/tao/cases/{cid}/versions/{version}')
    def get_version(cid: str, version: int, u=Depends(staff)):
        with db.connection() as con:
            visible(con, cid, u)
            row = con.execute('SELECT * FROM tao_versions WHERE case_id=? AND version=?', (cid, version)).fetchone()
            if not row:
                raise HTTPException(404, 'A verzió nem található.')
            return {'version': version, 'data': json.loads(row['data']), 'calculation': json.loads(row['calculation']), 'approved_at': row['approved_at']}

    @router.post('/api/tao/cases/{cid}/approve')
    def approve(cid: str, payload: Approval, u=Depends(reviewer)):
        if not all((payload.relationships, payload.rules, payload.scope)):
            raise HTTPException(422, 'A tényállás, jogi időállapot és vizsgálati kör ellenőrzése szükséges.')
        with db.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            case = visible(con, cid, u)
            if payload.version != case['version']:
                raise HTTPException(409, 'A Tao-vizsgálat verziója megváltozott.')
            if case['status'].startswith('approved'):
                raise HTTPException(409, 'Ez a verzió már jóváhagyott.')
            data = TaoAssessment.model_validate_json(case['data'])
            calc = calculate(data)
            if not calc['law_profile_present']:
                raise HTTPException(422, 'Rögzítse az ellenőrzött jogi időállapotot és forrását.')
            if not data.scope:
                raise HTTPException(422, 'Rögzítse a vállalt vizsgálati kört.')
            if not calc['complete'] and not payload.partial:
                raise HTTPException(422, 'Nem eldöntött cégpárok vannak. Részleges állásfoglalás adható, kifejezett indokkal.')
            if payload.partial and not payload.note:
                raise HTTPException(422, 'A részleges állásfoglalás korlátait röviden rögzíteni kell.')
            if con.execute('SELECT count(*) FROM tao_documents WHERE case_id=? AND reviewed_at IS NULL', (cid,)).fetchone()[0]:
                raise HTTPException(422, 'Feldolgozatlan forrásirat van. Előbb ellenőrizze a dokumentumokat.')
            stamp = db.now()
            status = 'approved_complete' if calc['complete'] else 'approved_partial'
            con.execute('UPDATE tao_versions SET approved_at=?,approver=?,confirmations=?,calculation=? WHERE case_id=? AND version=?',
                        (stamp, u['id'], db.dumps(payload.model_dump()), db.dumps(calc), cid, case['version']))
            con.execute('UPDATE tao_cases SET status=?,approved_version=?,updated=? WHERE id=?', (status, case['version'], stamp, cid))
            tao_db.audit(con, cid, u['id'], 'approved', f'{case["version"]}. verzió; {status}. {payload.note}')
        return {'status': status, 'version': payload.version}

    @router.get('/api/tao/cases/{cid}/audit')
    def audit(cid: str, u=Depends(staff)):
        with db.connection() as con:
            visible(con, cid, u)
            return [dict(r) for r in con.execute('SELECT a.action,a.details,a.created,u.name AS actor FROM tao_audit a JOIN users u ON u.id=a.actor WHERE a.case_id=? ORDER BY a.id DESC', (cid,))]

    @router.get('/api/tao/cases/{cid}/documents')
    def documents(cid: str, u=Depends(user)):
        with db.connection() as con:
            visible(con, cid, u)
            return [dict(r) for r in con.execute('SELECT id,filename,size,sha256,created,reviewed_at FROM tao_documents WHERE case_id=?' + (' AND author=?' if u['role'] == 'client' else '') + ' ORDER BY created DESC',
                                               (cid, u['id']) if u['role'] == 'client' else (cid,))]

    @router.post('/api/tao/cases/{cid}/documents')
    async def upload(cid: str, file: UploadFile = File(...), u=Depends(user)):
        filename = Path((file.filename or 'dokumentum').replace('\\', '/')).name[:200]
        ext = Path(filename).suffix.lower()
        if ext not in ('.pdf', '.docx', '.xlsx', '.png', '.jpg', '.jpeg', '.txt'):
            raise HTTPException(422, 'PDF, DOCX, XLSX, PNG, JPG vagy TXT szükséges.')
        raw = await file.read(20 * 1024 * 1024 + 1)
        if not raw or len(raw) > 20 * 1024 * 1024:
            raise HTTPException(422 if not raw else 413, 'Üres vagy 20 MB-nál nagyobb fájl nem tölthető fel.')
        did = str(uuid4())
        folder = db.data_dir() / 'uploads' / 'tao'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (did + ext)
        try:
            with db.connection() as con:
                con.execute('BEGIN IMMEDIATE')
                case = visible(con, cid, u)
                path.write_bytes(raw)
                con.execute('INSERT INTO tao_documents(id,case_id,filename,stored_name,size,sha256,author,created) VALUES(?,?,?,?,?,?,?,?)',
                            (did, cid, filename, path.name, len(raw), hashlib.sha256(raw).hexdigest(), u['id'], db.now()))
                data = TaoAssessment.model_validate_json(case['data'])
                for decision in data.decisions:
                    decision.confirmed = False
                for family in data.family_facts:
                    family.confirmed = False
                for company in data.companies:
                    company.registry_reviewed_on = None
                version, calc = advance(con, case, data, u['id'])
                tao_db.audit(con, cid, u['id'], 'document_uploaded', filename + '; újraellenőrzés szükséges.')
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {'id': did, 'filename': filename, 'version': version}

    @router.post('/api/tao/cases/{cid}/documents/{did}/review')
    def review_document(cid: str, did: str, u=Depends(staff)):
        with db.connection() as con:
            visible(con, cid, u)
            result = con.execute('UPDATE tao_documents SET reviewed_at=?,reviewer=? WHERE id=? AND case_id=?', (db.now(), u['id'], did, cid))
            if not result.rowcount:
                raise HTTPException(404, 'A dokumentum nem található.')
            tao_db.audit(con, cid, u['id'], 'document_reviewed', did)
        return {'ok': True}

    @router.get('/api/tao/cases/{cid}/documents/{did}')
    def document(cid: str, did: str, u=Depends(user)):
        with db.connection() as con:
            visible(con, cid, u)
            row = con.execute('SELECT * FROM tao_documents WHERE case_id=? AND id=?', (cid, did)).fetchone()
            if not row or (u['role'] == 'client' and row['author'] != u['id']):
                raise HTTPException(404, 'A dokumentum nem található.')
        return FileResponse(db.data_dir() / 'uploads' / 'tao' / row['stored_name'], filename=row['filename'], media_type='application/octet-stream')

    @router.get('/api/tao/cases/{cid}/report/{kind}')
    def report(cid: str, kind: str, version: int | None = None, u=Depends(user)):
        if kind not in ('xlsx', 'docx', 'pdf'):
            raise HTTPException(404, 'Ismeretlen exportformátum.')
        with db.connection() as con:
            case = visible(con, cid, u)
            v = version or (case['approved_version'] if u['role'] == 'client' else case['version'])
            row = con.execute('SELECT v.*,u.name AS approver_name FROM tao_versions v LEFT JOIN users u ON u.id=v.approver WHERE case_id=? AND version=?', (cid, v)).fetchone()
            if not row or (u['role'] == 'client' and (not row['approved_at'] or kind == 'xlsx')):
                raise HTTPException(404, 'Jóváhagyott állásfoglalás még nem érhető el.')
            data = TaoAssessment.model_validate_json(row['data'])
            calc = json.loads(row['calculation'])
            approved = bool(row['approved_at'])
            meta = {'id': cid, 'version': v, 'approved': approved, 'approved_at': row['approved_at'],
                    'approver': row['approver_name'], 'note': json.loads(row['confirmations'])['note'] if row['confirmations'] else '',
                    'label': ('Jóváhagyott teljes állásfoglalás' if calc['complete'] else 'Jóváhagyott részleges állásfoglalás') if approved else 'TERVEZET'}
        if kind == 'xlsx':
            output = Response(xlsx_report(data, calc, meta), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                              headers={'Content-Disposition': f'attachment; filename="Tao_matrix_v{v}.xlsx"'})
        else:
            folder = db.data_dir() / 'exports' / 'tao'
            folder.mkdir(parents=True, exist_ok=True)
            stem = f'{cid}-v{v}-' + ('approved' if approved else 'draft')
            path = folder / (stem + '.docx')
            if not path.exists():
                with tempfile.NamedTemporaryFile(dir=folder, delete=False) as temp:
                    temp.write(word_report(data, calc, meta))
                    pending = Path(temp.name)
                os.replace(pending, path)
            if kind == 'pdf':
                path = folder / (stem + '.pdf')
                if not path.exists():
                    try:
                        with tempfile.TemporaryDirectory(dir=folder) as temp_dir:
                            subprocess.run([configured_tool('soffice') or 'soffice', f'-env:UserInstallation={Path(temp_dir).as_uri()}/profile', '--headless', '--convert-to', 'pdf', '--outdir', temp_dir, str(folder / (stem + '.docx'))],
                                           check=True, timeout=60, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            pdf = Path(temp_dir) / (stem + '.pdf')
                            if not pdf.exists():
                                raise RuntimeError('Nem keletkezett PDF.')
                            os.replace(pdf, path)
                    except (OSError, subprocess.SubprocessError, RuntimeError):
                        raise HTTPException(503, 'A PDF-konverzió nem sikerült. A Word-export elérhető.')
            output = FileResponse(path, filename=f'Tao_allasfoglalas_v{v}.{kind}', media_type='application/pdf' if kind == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        with db.connection() as con:
            tao_db.audit(con, cid, u['id'], 'report_downloaded', f'{v}. verzió; {kind}; {meta["label"]}')
        return output

    @router.get('/tao')
    def page():
        return FileResponse(Path(__file__).parent / 'static' / 'tao.html')

    return router
