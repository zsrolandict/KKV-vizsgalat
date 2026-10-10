"""Tao 4(23)(d/e) PE signals; trust roles remain distinct from voting rights."""
from collections import defaultdict
from .tao_control import current_or_pending


def apply_special(data, rows, active):
    lookup = {frozenset((r['first'], r['second'])): r for r in rows}
    names = {x.id: x.name for x in [*data.companies, *data.persons]}
    decisions = {frozenset((d.first, d.second)): d for d in data.decisions if d.as_of == data.as_of}
    def abc(first, second):
        decision = decisions.get(frozenset((first, second)))
        if decision and decision.confirmed:
            return decision.result == 'related' and decision.legal_ground == 'abc'
        row = lookup.get(frozenset((first, second)))
        return bool(row and row.get('abc_signal'))
    def add(first, second, signal='', missing='', pe=None, trust=None):
        row = lookup.get(frozenset((first, second)))
        if not row:
            return
        if signal and signal not in row['signals']:
            row['signals'].append(signal)
            if not row['confirmed'] and row['stage'] != 'expert_draft':
                row['stage'], row['stage_label'] = 'special_signal', 'Telephelyi kapcsoltsági jelzés'
                row['reason'] = 'Telephelyi kapcsoltsági jogalap jelzése; külön szakértői jogi döntés szükséges.'
        if missing and missing not in row['missing']:
            row['missing'].append(missing)
            if not row['confirmed'] and not row['signals'] and row['stage'] != 'expert_draft':
                row['stage'], row['stage_label'] = 'missing_data', 'Hiányzó adat'
                row['reason'] = 'A BVK- vagy telephelyi tényállás és jogalap további ellenőrzést igényel.'
        for key, fact in [('establishment_facts', pe), ('trust_facts', trust)]:
            values = row.setdefault(key, [])
            if fact and not any(v['id'] == fact.id for v in values):
                values.append(fact.model_dump(mode='json'))
    grouped = defaultdict(list)
    for fact in data.establishment_facts:
        if current_or_pending(fact, data.as_of):
            grouped[fact.establishment].append(fact)
    eligible = []
    for estate, facts in grouped.items():
        signatures = {(f.principal, f.kind, f.tax_status) for f in facts if f.confirmed and active(f, data.as_of)}
        conflict = len(signatures) > 1
        for fact in facts:
            missing = ('Eltérő igazolt telephelyi források.' if conflict else
                       'A Tao-telephelyi jogállás vagy vizsgálati napi fennállás nem igazolt.'
                       if not (fact.confirmed and active(fact, data.as_of)) or fact.tax_status == 'unknown' else '')
            add(fact.principal, estate, missing=missing, pe=fact)
            if not missing and fact.tax_status == 'yes':
                eligible.append(fact)
    for fact in eligible:
        if fact.kind == 'other_foreign_business_pe':
            continue
        ground = 'd)' if fact.kind == 'foreign_business_domestic_pe' else 'e)'
        add(fact.principal, fact.establishment, f'Igazolt fővállalkozás–Tao-telephely viszony (Tao. 4. § 23. {ground}).', pe=fact)
        for company in data.companies:
            if company.id not in (fact.principal, fact.establishment) and abc(fact.principal, company.id):
                add(fact.establishment, company.id, f'A telephely fővállalkozásával, {names[fact.principal]} szereplővel a)–c) szerinti kapcsolat jelzett (Tao. 4. § 23. {ground}).', pe=fact)
        if fact.kind == 'foreign_business_domestic_pe':
            for other in eligible:
                if other.principal == fact.principal and other.establishment != fact.establishment and other.kind in ('foreign_business_domestic_pe', 'other_foreign_business_pe'):
                    add(fact.establishment, other.establishment, 'Ugyanazon külföldi vállalkozó igazolt telephelyei (Tao. 4. § 23. d)).', pe=fact)
                    add(fact.establishment, other.establishment, pe=other)
    for fact in data.trust_facts:
        if not current_or_pending(fact, data.as_of):
            continue
        relevant = set(fact.holdings) | set(fact.trustees) | set(fact.settlors) | set(fact.beneficiaries) | ({fact.asset_entity} if fact.asset_entity else set())
        for row in rows:
            if {row['first'], row['second']} & relevant:
                missing = '' if fact.confirmed and active(fact, data.as_of) and fact.rights_reviewed else f'{fact.name}: a vagyonelkülönítés és a tényleges szavazati/irányítási jogok ellenőrzése szükséges.'
                add(row['first'], row['second'], missing=missing, trust=fact)
    for fact in data.voting_facts:
        if fact.capacity != 'own' and not fact.attribution_reviewed and current_or_pending(fact, data.as_of):
            for row in rows:
                if fact.company in (row['first'], row['second']):
                    add(row['first'], row['second'], missing=f'{names[fact.owner]} → {names[fact.company]}: a BVK vagy tisztázatlan jogállású szavazatok hozzárendelése nincs ellenőrizve.')
