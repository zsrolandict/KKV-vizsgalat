"""OPTEN text-PDF candidates. Extraction never constitutes expert/legal approval."""
import re
import subprocess
from datetime import date
from hashlib import sha256
from pathlib import Path
from .tool_paths import configured_tool

PARSER_VERSION = 'opten-text-1'
DATE = r'\d{4}\.\d{2}\.\d{2}\.?'
ROW = re.compile(r'^\s*(\d+(?:\(\d+\))?/\d+)\s+', re.M)
HEADING = re.compile(r'^\s*\d+(?:\(\d+\))?\.\s+\S', re.M)


def iso(value):
    if not value or value.startswith('...'):
        return None
    try:
        return date.fromisoformat(value.rstrip('.').replace('.', '-')).isoformat()
    except ValueError:
        return None


def dates(text):
    found = re.search(r'Hatályos:\s*(' + DATE + r'|\.\.\.)\s*-\s*(' + DATE + r'|\.\.\.)', text)
    def named(label):
        m = re.search(label + r':\s*(' + DATE + ')', text)
        return iso(m[1]) if m else None
    return dict(valid_from=iso(found[1]) if found else None, valid_to=iso(found[2]) if found else None,
                registered_on=named('Bejegyzés kelte'), deletion_registered_on=named('Törlés kelte'))


def extract(path: Path, filename: str):
    if path.read_bytes()[:5] != b'%PDF-':
        raise ValueError('A fájl nem érvényes PDF.')
    tool = configured_tool('pdftotext')
    if not tool:
        raise RuntimeError('A PDF-kiolvasó nem található. Windowson indítsa az alkalmazást az Inditas-Windows.cmd fájllal, és adja meg a kicsomagolt Poppler mappáját. Linuxon a poppler-utils csomag szükséges.')
    try:
        run = subprocess.run([tool, '-layout', '-enc', 'UTF-8', str(path), '-'], capture_output=True, timeout=30)
    except FileNotFoundError:
        raise RuntimeError('A beállított PDF-kiolvasó nem indítható. Ellenőrizze a Poppler útvonalát, majd indítsa újra az alkalmazást.')
    except subprocess.TimeoutExpired:
        raise ValueError('A PDF feldolgozása túllépte a megengedett időt.')
    if run.returncode:
        raise ValueError('A PDF nem olvasható; lehet sérült vagy jelszóval védett.')
    if len(run.stdout) > 6 * 1024 * 1024:
        raise ValueError('Túl nagy kinyert szöveg. Kisebb dokumentum szükséges.')
    return parse_text(run.stdout.decode('utf-8', errors='replace'), filename)


def parse_text(text, filename='forras.pdf'):
    pages = text.split('\f')
    if len(pages) > 301:
        raise ValueError('Egy dokumentum legfeljebb 300 oldalas lehet.')
    if len(text.strip()) < 80:
        raise ValueError('Nem található kiolvasható szöveg. A szkennelt PDF-hez OCR szükséges.')
    reg = re.search(r'Cégjegyzékszám:\s*(\d{2})[ -]+(\d{2})[ -]+(\d{6})', pages[0])
    if not reg or not re.search(r'Cégadatlap|Cégtörténet', pages[0]):
        raise ValueError('Nem felismerhető OPTEN cégadatlap vagy cégtörténet.')
    registration = '-'.join(reg.groups())
    stamp = re.search(r'(\d{4})\.\s*(\d{2})\.\s*(\d{2})-i hatállyal', pages[0])
    name = next((line.strip() for line in pages[0].splitlines() if line.strip()), '')
    out = dict(name=name, registration=registration, source=filename, source_date='-'.join(stamp.groups()) if stamp else None,
               historical='Cégtörténet' in pages[0], page_count=len(pages) - (not pages[-1].strip()),
               owners=[], leaders=[], financials=[], aliases=[], reference_employees=None, warnings=[])
    for section in re.finditer(r'^\s*2/\d+\s+([^\n]+)', text, re.M):
        out['aliases'].append(section[1].strip())
    def proof(start, quote):
        return dict(source=filename, page=text[:start].count('\f') + 1, quote=quote[:3000])
    # Parse only the formal shareholder/member section, never banks, auditors or pledges.
    sections = list(HEADING.finditer(text))
    for idx, section in enumerate(sections):
        if not re.match(r'\s*1\((?:09|10)\)\.', section[0]):
            continue
        end = sections[idx + 1].start() if idx + 1 < len(sections) else len(text)
        body = text[section.end():end]
        gathered = body.find('Gyűjtött tulajdonosi információk')
        formal = body[:gathered] if gathered >= 0 else body
        rows = list(ROW.finditer(formal))
        for n, row in enumerate(rows):
            block = formal[row.end():rows[n+1].start() if n+1 < len(rows) else len(formal)].strip()
            first = block.splitlines()[0].strip()
            own_reg = re.match(r'\[(\d{2})[ -]+(\d{2})[ -]+(\d{6})\s*\]\s*', first)
            owner = first[own_reg.end():] if own_reg else first.split('(an:')[0].strip()
            # Wrapped company names end at the first metadata/address line.
            if own_reg:
                for line in block.splitlines()[1:]:
                    line = line.strip()
                    if not line or re.match(r'\(|HU-|\d{4}\s|A |Szavazati|Változás|Bejegyzés|Hatályos|Befolyás', line):
                        break
                    owner += ' ' + line
            qualitative = 'meghaladja az 50%-ot' in block or 'minősített többségű' in block
            capital = '100' if 'egyedüli részvényes' in block or 'egyedüli tag' in block else None
            raw_percent = re.search(r'Befolyás(?:olás)? mértéke(?:/Szavazatok száma)?:\s*([\d,.]+)%', block)
            out['owners'].append(dict(name=owner[:200], registration='-'.join(own_reg.groups()) if own_reg else '',
                capital=capital, vote_mode='explicit' if qualitative else 'ownership_default' if capital else 'unknown',
                votes=None, vote_bound='over_half' if qualitative else 'exact',
                raw_influence=raw_percent[1] if raw_percent else None, trustee='bizalmi vagyonkezelőként' in block,
                **dates(block), evidence=proof(section.end()+row.start(), block)))
        if gathered >= 0:
            collected = body[gathered + len('Gyűjtött tulajdonosi információk'):]
            for block in re.split(r'\n\s*\n', collected):
                lines = [x.strip() for x in block.splitlines() if x.strip()]
                if len(lines) < 2 or 'Forrás:' not in block or lines[0].startswith(('Forrás:', 'Hatályos:', 'Befolyás')):
                    continue
                owner = lines[0]
                if any(x['name'] == owner for x in out['owners']):
                    continue
                raw_percent = re.search(r'Befolyás(?:olás)? mértéke(?:/Szavazatok száma)?:\s*([\d,.]+)%', block)
                out['owners'].append(dict(name=owner[:200], registration='', capital=None, votes=None, vote_mode='unknown',
                    vote_bound='exact', raw_influence=raw_percent[1] if raw_percent else None, trustee=False,
                    **dates(block), evidence=proof(section.end()+gathered+body[gathered:].find(block), block.strip())))
    # Representation rows remain separate source candidates; common leadership is not a legal conclusion.
    rows = list(ROW.finditer(text))
    for n, row in enumerate(rows):
        if not row[1].startswith('13/'):
            continue
        end = min([m.start() for m in sections if m.start() > row.start()] + [rows[n+1].start() if n+1<len(rows) else len(text)])
        block = text[row.end():end].strip()
        person = re.match(r'(.+?)\s*\(an:', block)
        if person:
            role = 'cégvezető' if 'cégvezető' in block else 'ügyvezető' if 'ügyvezető' in block else 'vezető / képviselő'
            out['leaders'].append(dict(name=person[1].strip(), role=role, **dates(block), evidence=proof(row.start(), block)))
    for page_no, page in enumerate(pages, 1):
        years = re.search(r'((?:\d{4}\. év\s*){2,})', page)
        if not years:
            continue
        columns = [int(y) for y in re.findall(r'(\d{4})\. év', years[1])]
        money = {}
        starts = re.search(r'Beszámolási időszak([^\n]+)', page)
        ends = re.search(r'Értékek: Ezer HUF-ban([^\n]+)', page)
        period_starts = re.findall(DATE, starts[1]) if starts else []
        period_ends = re.findall(DATE, ends[1]) if ends else []
        if len(period_starts) != len(columns) or len(period_ends) != len(columns):
            out['warnings'].append(f'{page_no}. oldal: a beszámolási időszakok kézi ellenőrzést igényelnek.')
        for key, label in [('turnover', 'Értékesítés nettó árbevétele'), ('balance', 'Eszközök összesen')]:
            row = re.search(re.escape(label) + r'([^\n]+)', page)
            if row:
                values = re.split(r'\s{2,}', row[1].strip())
                if len(values) == len(columns) and 'Ezer HUF' in page:
                    money[key] = [v.replace(' ', '') if re.fullmatch(r'\d[\d ]*', v) else None for v in values]
                    if any(v is None for v in money[key]):
                        out['warnings'].append(f'{page_no}. oldal: {label} egyes értékei hiányoznak vagy kézi értelmezést igényelnek.')
                else:
                    out['warnings'].append(f'{page_no}. oldal: {label} oszlopai vagy pénzneme kézi ellenőrzést igényelnek.')
        if money:
            for i, year in enumerate(columns):
                out['financials'].append(dict(year=year, turnover=money.get('turnover', [None]*len(columns))[i],
                    balance=money.get('balance', [None]*len(columns))[i], employees=None, unit='ezer HUF',
                    start=iso(period_starts[i]) if len(period_starts)==len(columns) else None,
                    end=iso(period_ends[i]) if len(period_ends)==len(columns) else None,
                    evidence=dict(source=filename, page=page_no, quote='Pénzügyi modul – értékek ezer HUF-ban.')))
    count = re.search(r'Létszám:\s*(\d+)\s*fő', text)
    if count:
        out['reference_employees'] = dict(value=count[1], **proof(count.start(), count[0]))
    out['warnings'].append('A rokonság, irányítási megállapodás és döntő üzleti/pénzügyi irányítás külön ellenőrzendő.')
    if not out['owners']:
        out['warnings'].append('A tulajdonosi kör nem volt kiolvasható; ez nem bizonyít függetlenséget.')
    if any(o['raw_influence'] is not None for o in out['owners']):
        out['warnings'].append('A gyűjtött befolyási százalék nem került automatikusan tulajdoni vagy szavazati arányba.')
    return out


def entity_id(registration, name):
    return 'pdf-' + sha256((registration or name.casefold()).encode()).hexdigest()[:20]
