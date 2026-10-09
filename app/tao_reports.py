from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .tao_models import FAMILY_LABELS, CONTROL_LABELS, PE_LABELS
from .tao_engine import RESULT_LABELS


ANSWER_LABELS = {'yes': 'Igen', 'no': 'Nem', 'unknown': 'Tisztázandó'}
MEMBERSHIP_LABELS = {'member': 'Tag / részvényes', 'not_member': 'Nem tag / részvényes', 'unknown': 'Tisztázandó'}


def evidence_text(evidence):
    source = evidence.get('source', '')
    if evidence.get('page'):
        source += f' · {evidence["page"]}. oldal'
    if evidence.get('quote'):
        source += '\nIdézet: ' + evidence['quote']
    return source


def text_cell(value):
    # Force literal strings, including user text starting with '=' or '+'.
    return str(value if value is not None else '')


def xlsx_report(data, calc, meta):
    wb = Workbook()
    matrix = wb.active
    matrix.title = 'Mátrix'
    matrix.append(['Vizsgálat', data.title])
    matrix.append(['Vizsgálati nap', data.as_of.isoformat()])
    matrix.append(['Állapot', meta['label']])
    matrix.append(['Értékelés', 'Szakértői döntések; a szavazati és irányítási jelzések nem végleges jogi minősítések.'])
    matrix.append([])
    matrix.append(['Vállalkozás', *[c.name for c in data.companies]])
    lookup = {frozenset((r['first'], r['second'])): r for r in calc['rows']}
    for a in data.companies:
        matrix.append([a.name, *['—' if a.id == b.id else lookup[frozenset((a.id, b.id))]['label'] for b in data.companies]])
    matrix.freeze_panes = 'B7'
    details = wb.create_sheet('Indokolások')
    details.append(['Cég A', 'Cég B', 'Jogi eredmény', 'Munkafolyamat', 'Jogalap', 'Indok', 'Forrás / oldal', 'Feltételezés', 'Hiányzó adat', 'Kapcsoltsági jelzés'])
    for row in calc['rows']:
        details.append([row['first_name'], row['second_name'], row['label'], row['stage_label'], row['basis'], row['reason'],
                        evidence_text(row['evidence']), '\n'.join(row['assumptions']), '\n'.join(row['missing']), '\n'.join(row['signals'])])
    details.freeze_panes = 'C2'
    details.auto_filter.ref = details.dimensions
    computations = wb.create_sheet('Befolyásszámítás')
    computations.append(['Cég A', 'Cég B', 'Jogosult', 'Célcég', 'Befolyás', 'Többség igazolt', 'Joghely', 'Tényazonosítók'])
    actor_names = {x.id: x.name for x in [*data.companies, *data.persons]}
    for row in calc['rows']:
        for value in row.get('influence_calculations', []):
            computations.append([row['first_name'], row['second_name'], value.get('owner_name') or actor_names[value['owner']],
                                 actor_names[value['company']], value['value'], 'Igen' if value['majority'] else 'Nem',
                                 value['basis'], ', '.join(value['fact_ids'])])
    facts = wb.create_sheet('Szavazati források')
    names = {x.id: x.name for x in [*data.companies, *data.persons]}
    facts.append(['Tulajdonos', 'Célcég', 'Tőke (%)', 'Szavazati mód', 'Szavazat (%) / feltétel', 'Kezdet', 'Vége (kizáró)', 'Ellenőrzött nap', 'Forrás', 'Indok', 'Tényazonosító', 'Részesedés jogállása', 'BVK-hozzárendelés ellenőrizve'])
    for fact in data.voting_facts:
        vote = '>50%' if fact.vote_bound == 'over_half' else fact.votes
        facts.append([names[fact.owner], names[fact.company], fact.capital, fact.vote_mode, vote,
                      fact.valid_from, fact.valid_to, fact.reviewed_as_of, fact.evidence.source, fact.reason, fact.id, fact.capacity, str(fact.attribution_reviewed)])
    relatives = wb.create_sheet('Rokonsági források')
    relatives.append(['Első személy', 'Második személy', 'Viszony', 'Kezdet', 'Vége (kizáró)', 'Ellenőrzött nap', 'Igazolt', 'Forrás / oldal', 'Tényazonosító'])
    for fact in data.family_facts:
        relatives.append([names[fact.first], names[fact.second], FAMILY_LABELS[fact.relationship],
                          fact.valid_from, fact.valid_to, fact.reviewed_as_of,
                          'Igen' if fact.confirmed else 'Nem', evidence_text(fact.evidence.model_dump(mode='json')), fact.id])
    rights = wb.create_sheet('Irányítási jogok')
    rights.append(['Jogosult', 'Célcég', 'Jogcím', 'Tagi jogállás', 'Feltétel fennáll', 'Együttes szavazat (%)', 'Igazolt', 'Indok', 'Forrás / oldal', 'Kezdet', 'Vége (kizáró)', 'Ellenőrzött nap', 'Tényazonosító'])
    for fact in data.control_facts:
        rights.append([names[fact.owner], names[fact.company], CONTROL_LABELS[fact.kind], MEMBERSHIP_LABELS[fact.membership],
                       ANSWER_LABELS[fact.condition], '>50%' if fact.aligned_bound == 'over_half' else fact.aligned_votes, 'Igen' if fact.confirmed else 'Nem', fact.reason,
                       evidence_text(fact.evidence.model_dump(mode='json')), fact.valid_from, fact.valid_to,
                       fact.reviewed_as_of, fact.id])
    managers = wb.create_sheet('Ügyvezetési tények')
    managers.append(['Cég A', 'Cég B', 'Közös vezetők', 'Egyezőség', 'Üzleti döntő befolyás', 'Pénzügyi döntő befolyás', 'Igazolt', 'Indok', 'Forrás / oldal', 'Kezdet', 'Vége (kizáró)', 'Ellenőrzött nap', 'Tényazonosító'])
    for fact in data.management_facts:
        managers.append([names[fact.first], names[fact.second], ', '.join(names[m] for m in fact.managers),
                         ANSWER_LABELS[fact.common_management], ANSWER_LABELS[fact.business_control], ANSWER_LABELS[fact.financial_control],
                         'Igen' if fact.confirmed else 'Nem', fact.reason, evidence_text(fact.evidence.model_dump(mode='json')),
                         fact.valid_from, fact.valid_to, fact.reviewed_as_of, fact.id])
    routes = wb.create_sheet('Irányítási útvonalak')
    routes.append(['Cég A', 'Cég B', 'Jogosult', 'Célcég', 'Útvonal', 'Jogalap', 'Irányítási tények', 'Szavazati tények'])
    for row in calc['rows']:
        for route in row.get('control_calculations', []):
            routes.append([row['first_name'], row['second_name'], names[route['owner']], names[route['company']],
                           ' → '.join(names[n] for n in route['route']), route['basis'],
                           ', '.join(route['control_ids']), ', '.join(route['fact_ids'])])
    pe = wb.create_sheet('Tao-telephelyek')
    pe.append(['Fővállalkozás','Telephely','Jogviszony','Adójogi jogállás','Igazolt','Indok','Forrás','Kezdet','Vége','Ellenőrzött nap'])
    for f in data.establishment_facts:
        pe.append([names[f.principal],names[f.establishment],PE_LABELS[f.kind],ANSWER_LABELS[f.tax_status],str(f.confirmed),f.reason,evidence_text(f.evidence.model_dump(mode='json')),f.valid_from,f.valid_to,f.reviewed_as_of])
    trusts = wb.create_sheet('BVK-tények')
    trusts.append(['Kezelt vagyon','Vagyonkezelők','Vagyonrendelők','Kedvezményezettek','Érintett cégek','Jogok ellenőrizve','Indok','Forrás'])
    for f in data.trust_facts:
        trusts.append([f.name,', '.join(names[x] for x in f.trustees),', '.join(names[x] for x in f.settlors),', '.join(names[x] for x in f.beneficiaries),', '.join(names[x] for x in f.holdings),str(f.rights_reviewed),f.reason,evidence_text(f.evidence.model_dump(mode='json'))])
    profile = wb.create_sheet('Vizsgálati keret')
    for key, value in [('Ügyazonosító', meta['id']), ('Verzió', meta['version']), ('Állapot', meta['label']),
                       ('Vizsgálati cél', data.purpose), ('Vállalt vizsgálati kör', data.scope),
                       ('Feltételezések', data.assumptions), ('Jogi időállapot', data.law_date),
                       ('Történeti alkalmazhatóság', data.law_applicability), ('Jogi forrás', data.law_source), ('Munkafolyamat-verzió', calc['rule_version']),
                       ('Jóváhagyó', meta.get('approver') or ''), ('Jóváhagyás', meta.get('approved_at') or '')]:
        profile.append([key, value])
    for sheet in wb:
        for row in sheet:
            for cell in row:
                cell.value = text_cell(cell.value)
                cell.data_type = 's'
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='1C3658')
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = 26
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def word_report(data, calc, meta):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2)
    section.header.paragraphs[0].text = 'TAO / SZAKÉRTŐI VIZSGÁLAT · ' + meta['label']
    section.footer.paragraphs[0].text = f'{meta["id"]} · {meta["version"]}. verzió · {calc["rule_version"]}'
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(10)
    for heading in ('Heading 1', 'Heading 2'):
        doc.styles[heading].font.color.rgb = RGBColor.from_string('1C3658')
    doc.add_heading('Tao szerinti kapcsoltsági vizsgálat', 0)
    doc.add_paragraph(data.title, style='Subtitle')
    doc.add_paragraph(meta['label']).runs[0].bold = True
    if not meta['approved']:
        doc.add_paragraph('TERVEZET – szakértői jóváhagyás nélkül végleges állásfoglalásként nem használható.')
    elif not calc['complete']:
        doc.add_paragraph('RÉSZLEGES ÁLLÁSFOGLALÁS – a nem eldöntött cégpárok nem minősülnek nem kapcsoltnak.').runs[0].bold = True
    doc.add_paragraph(f'Megbízó: {data.client or "nincs megadva"}\nVizsgálati nap: {data.as_of}\nCél: {data.purpose}')
    doc.add_heading('Vizsgálati keret', 1)
    doc.add_paragraph(data.scope or 'A felsorolt vállalkozások egymás közötti kapcsoltsági vizsgálata.')
    doc.add_paragraph('A szavazati jelzések adat-előkészítési segítséget adnak. A jogi eredmények a rögzített szakértői döntésekből származnak; nem automatikus törvényi gráfminősítések.')
    doc.add_paragraph(f'Jogi időállapot: {data.law_date or "ellenőrizendő"}\nForrás: {data.law_source or "nincs rögzítve"}')
    doc.add_paragraph('Történeti alkalmazhatóság: '+(data.law_applicability or 'külön indok nincs rögzítve'))
    if data.assumptions:
        doc.add_paragraph('Feltételezések: ' + data.assumptions)
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Light Shading Accent 1'
    for cell, label in zip(table.rows[0].cells, ('Cég A', 'Cég B', 'Jogi eredmény')):
        cell.text = label
    for row in calc['rows']:
        for cell, value in zip(table.add_row().cells, (row['first_name'], row['second_name'], row['label'])):
            cell.text = value
    doc.add_heading('Cégpáronkénti indokolás', 1)
    for row in calc['rows']:
        doc.add_heading(row['first_name'] + ' – ' + row['second_name'], 2)
        doc.add_paragraph(f'{row["label"]} · {row["stage_label"]}')
        if row['basis']:
            doc.add_paragraph('Jogalap: ' + row['basis'])
        doc.add_paragraph(row['reason'])
        if row['evidence']:
            doc.add_paragraph('Forrás: ' + evidence_text(row['evidence']))
        actor_names = {x.id: x.name for x in [*data.companies, *data.persons]}
        for value in row.get('influence_calculations', []):
            doc.add_paragraph(f"Befolyásszámítás: {value.get('owner_name') or actor_names[value['owner']]} → {actor_names[value['company']]}: {value['value']} · {value['basis']} · Tények: {', '.join(value['fact_ids'])}")
        for fact in row.get('family_facts', []):
            doc.add_paragraph(f"Igazolt rokonság: {actor_names[fact['first']]} – {actor_names[fact['second']]} · {FAMILY_LABELS[fact['relationship']]} · {evidence_text(fact['evidence'])}")
        for route in row.get('control_calculations', []):
            doc.add_paragraph('Meghatározó befolyás útvonala: ' + ' → '.join(actor_names[n] for n in route['route']) + ' · ' + route['basis'])
        for fact in row.get('control_facts', []):
            doc.add_paragraph(f"Irányítási tény: {actor_names[fact['owner']]} → {actor_names[fact['company']]} · {CONTROL_LABELS[fact['kind']]} · Tagi jogállás: {MEMBERSHIP_LABELS[fact['membership']]} · Feltétel: {ANSWER_LABELS[fact['condition']]}")
            if fact['kind'] == 'voting_agreement':
                vote = '>50%' if fact['aligned_bound'] == 'over_half' else str(fact['aligned_votes']) + '%' if fact['aligned_votes'] is not None else 'Tisztázandó'
                doc.add_paragraph('Megállapodás szerinti együttes szavazat: ' + vote)
            doc.add_paragraph(fact['reason'] + ' · ' + evidence_text(fact['evidence']))
        for fact in row.get('management_facts', []):
            doc.add_paragraph('Ügyvezetési tény: ' + ', '.join(actor_names[m] for m in fact['managers']) + f" · Egyezőség: {ANSWER_LABELS[fact['common_management']]} · Üzleti döntő befolyás: {ANSWER_LABELS[fact['business_control']]} · Pénzügyi döntő befolyás: {ANSWER_LABELS[fact['financial_control']]}")
            doc.add_paragraph(fact['reason'] + ' · ' + evidence_text(fact['evidence']))
        for f in row.get('establishment_facts', []):
            doc.add_paragraph('Telephelyi tény: ' + actor_names[f['principal']] + ' → ' + actor_names[f['establishment']] + ' · ' + PE_LABELS[f['kind']] + ' · ' + f['reason'] + ' · ' + evidence_text(f['evidence']))
        for f in row.get('trust_facts', []):
            doc.add_paragraph('BVK: ' + f['name'] + ' · ' + f['reason'] + ' · ' + evidence_text(f['evidence']))
        for label, values in (('Kapcsoltsági jelzés', row['signals']), ('Feltételezés', row['assumptions']), ('Tisztázandó', row['missing'])):
            for value in values:
                doc.add_paragraph(label + ': ' + value)
    doc.add_heading('Jóváhagyás és visszakövethetőség', 1)
    if meta['approved']:
        stamp = datetime.fromisoformat(meta['approved_at']).astimezone(ZoneInfo('Europe/Budapest')).strftime('%Y.%m.%d. %H:%M')
        doc.add_paragraph(f'Jóváhagyó: {meta["approver"]}\nJóváhagyás: {stamp} (Europe/Budapest)')
        if meta.get('note'):
            doc.add_paragraph(meta['note'])
    else:
        doc.add_paragraph('Szakértői jóváhagyás még nem történt.')
    doc.add_paragraph('A KKV-minősítés és a transzferár-kötelezettség külön vizsgálat. A rendszerbeli jóváhagyás nem elektronikus aláírás.')
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()
