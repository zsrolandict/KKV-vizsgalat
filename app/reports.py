from io import BytesIO
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .engine import LABELS


def hu(value, decimals=2):
    if value is None:return '–'
    v=Decimal(str(value))
    s=f'{v:,.{decimals}f}'.replace(',', '\u00a0').replace('.', ',')
    return s.rstrip('0').rstrip(',') if decimals else s


def word_report(data, calculation, metadata):
    doc=Document()
    for s in doc.sections:
        s.top_margin=s.bottom_margin=Cm(2)
        s.left_margin=s.right_margin=Cm(2)
        s.header.paragraphs[0].text='KKV / SZAKÉRTŐI ÁLLÁSFOGLALÁS' + ('' if metadata['approved'] else ' · TERVEZET')
        s.footer.paragraphs[0].text=f"Ügy: {metadata['id']} · {metadata['version']}. verzió · {calculation['rule_version']}"
    normal=doc.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(10)
    for n in ['Heading 1','Heading 2']:
        doc.styles[n].font.color.rgb=RGBColor.from_string('234B3F')
    root=next(c for c in data.companies if c.id==data.root)
    doc.add_heading('Állásfoglalás a vállalkozás KKV-minősítéséről',0)
    doc.add_paragraph(root.name,style='Subtitle')
    if not metadata['approved']:
        doc.add_paragraph('TERVEZET – szakértői jóváhagyás nélkül végleges állásfoglalásként nem használható.').runs[0].bold=True
    doc.add_paragraph(f'Vizsgálat napja: {data.as_of.isoformat()} · Profil: {"Magyar Kkv. törvény" if data.profile=="HU" else "EU KKV-definíció"}')
    doc.add_heading('Feladat és alapadatok',1)
    doc.add_paragraph(data.purpose)
    if data.client:doc.add_paragraph(f'Megbízó: {data.client}')
    doc.add_paragraph('A vizsgált időszakok: '+', '.join(map(str,sorted(data.years)))+'. A számítás a rögzített kapcsolati és beszámolóadatokból készült.')
    doc.add_paragraph('Cégháló időpontja: '+('az egyes beszámolási időszakok zárónapja.' if data.structure_basis=='period_end' else 'a vizsgálat napja; a szakértő által kiválasztott alkalmazási mód.'))
    doc.add_heading('Kapcsolatok és összeszámítás',1)
    last=calculation['years'][-1] if calculation['years'] else None
    if last:
        table=doc.add_table(rows=1,cols=4);table.style='Light Shading Accent 1'
        for cell,t in zip(table.rows[0].cells,['Vállalkozás','Jogcím','Arány','Indok']):cell.text=t
        relation={'own':'Saját','linked':'Kapcsolódó','partner':'Partner','independent':'Kizárt / önálló','consolidated':'Konszolidált'}
        for row in last['rows']:
            for cell,t in zip(table.add_row().cells,[row['name'],relation[row['relation']],hu(row['percent'])+'%',row['reason']]):cell.text=t
    names={c.id:c.name for c in data.companies}
    for decision in data.decisions:
        interval=f'{decision.start or "kezdet nincs megadva"} – {decision.end or "vég nincs megadva"}'
        summary=f'{names[decision.first]} – {names[decision.second]}: {decision.reason}. Forrás: {decision.source or "nincs rögzítve"}. Rögzített időszak: {interval}.'
        if decision.basis=='persons':
            summary += f' Közös fellépés: {decision.acting_together}; piaci viszony: {decision.market}.'
        if not decision.confirmed:summary += ' Szakértői ellenőrzésre vár.'
        doc.add_paragraph(summary)
    doc.add_heading('Éves adatok és méretbesorolás',1)
    table=doc.add_table(rows=1,cols=5);table.style='Light Shading Accent 1'
    for cell,t in zip(table.rows[0].cells,['Év','Létszám','Árbevétel (ezer Ft)','Mérleg (ezer Ft)','Éves méret']):cell.text=t
    for y in calculation['years']:
        totals=y['totals']
        values=[str(y['year']),hu(totals['employees']),hu(Decimal(totals['turnover'])/1000),hu(Decimal(totals['balance'])/1000),y['label']]
        for cell,t in zip(table.add_row().cells,values):cell.text=t
        rate=next((r for r in data.rates if r.year==y['year']),None)
        if rate:doc.add_paragraph(f"{y['year']}: {hu(rate.value,8)} HUF/EUR; érvényesség: {rate.date.isoformat()}; jegyzés: {rate.quoted.isoformat() if rate.quoted else 'nincs megadva'}; forrás: {rate.source}.")
    doc.add_paragraph('A besorolás a kerekítés előtti értékekből készült. A pénzügyi feltételek között VAGY, a létszám és a pénzügyi feltétel között ÉS kapcsolat szerepel.')
    doc.add_heading('Kétéves szabály és hatályos minősítés',1)
    if data.previous_category:
        doc.add_paragraph(f'Korábbi minősítés: {LABELS[data.previous_category]}, referencia: {data.previous_date}.')
    for h in calculation['history']:
        doc.add_paragraph(f"{h['year']}: éves méret: {LABELS.get(h['annual'],'hiányos')}; történeti állapot: {LABELS.get(h['effective'],'további előzmény szükséges')}"+('; átmeneti megfigyelés folyamatban.' if h['pending'] else '.'))
    for e in data.events:doc.add_paragraph(f'{e.date}: {e.description}. Szakértői kezelés: {e.resolution or "tisztázandó"}.')
    doc.add_heading('Megállapítás',1)
    doc.add_paragraph(f"A rögzített adatok és feltételek alapján megállapított minősítés: {calculation['label']}.").runs[0].bold=True
    doc.add_paragraph(calculation['transfer_pricing'])
    if data.conclusion_notes:doc.add_paragraph(data.conclusion_notes)
    doc.add_heading('Feltételezések, források és ellenőrzések',1)
    doc.add_paragraph(data.assumptions or 'A minősítés a megadott adatokon alapul. A tényállás változása új vizsgálatot igényel.')
    sources=sorted(set(f.source for f in data.financials if f.source))
    for source in sources:doc.add_paragraph(source,style='List Bullet')
    for item in calculation['blockers']:doc.add_paragraph('Tisztázandó: '+item['message'],style='List Bullet')
    for warning in calculation['warnings']:doc.add_paragraph(warning,style='List Bullet')
    doc.add_heading('Alkalmazott jogi keret és jóváhagyás',1)
    doc.add_paragraph('2004. évi XXXIV. törvény; EU-profilnál a 2003/361/EK ajánlás és a vizsgálat céljára alkalmazandó uniós rendelkezések. Az alkalmazandó időállapotot és a szabályok ügyre való alkalmazhatóságát a jóváhagyó szakértő ellenőrzi. Transzferárnál az adott adóév Tao.- és nyilvántartási szabályai külön vizsgálandók.')
    if metadata['approved']:
        approved_stamp=datetime.fromisoformat(metadata['approved_at']).astimezone(ZoneInfo('Europe/Budapest')).strftime('%Y.%m.%d. %H:%M')
        doc.add_paragraph(f"Jóváhagyó szakértő: {metadata['approver']}\nJóváhagyás: {approved_stamp} (Europe/Budapest)\nSzámítási szabályverzió: {calculation['rule_version']}")
        doc.add_paragraph('A rendszerbeli jóváhagyás nem elektronikus aláírás. A dokumentum aláírása a szolgáltató munkafolyamata szerint történik.')
    else:doc.add_paragraph('Jóváhagyás: még nem történt meg.')
    for table in doc.tables:
        repeat=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:run.font.size=Pt(8)
    out=BytesIO();doc.save(out);return out.getvalue()
