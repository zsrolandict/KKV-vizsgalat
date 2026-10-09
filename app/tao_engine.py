"""Date-specific voting influence signals with expert legal decisions taking priority."""
from collections import defaultdict
from itertools import combinations
from .tao_influence import influence_graph
from .tao_family import family_groups
from .tao_models import CLOSE_FAMILY_TYPES

RULE_VERSION = 'TAO-munkafolyamat-1.2-igazolt-rokonsag'
RESULT_LABELS = {'related': 'Kapcsolt', 'not_related': 'Nem kapcsolt', 'undetermined': 'Nem dönthető el'}
STAGE_LABELS = {
    'unreviewed': 'Iratellenőrzésre vár',
    'awaiting_declaration': 'Nyilatkozatra vár',
    'missing_data': 'Hiányzó adat',
    'management_review': 'Közös vezetés – irányítás tisztázandó',
    'voting_signal': 'Többségi szavazati jelzés',
    'expert_draft': 'Szakértői döntés megerősítésre vár',
    'expert': 'Szakértői döntés',
}


def active(fact, day):
    # A missing beginning is usable only on the explicitly reviewed day.
    start_ok = fact.valid_from <= day if fact.valid_from else fact.reviewed_as_of == day
    return start_ok and (fact.valid_to is None or day < fact.valid_to)


def effective_vote(fact):
    if fact.vote_mode == 'ownership_default':
        return fact.capital
    if fact.vote_mode in ('explicit', 'expert'):
        return '>50' if fact.vote_bound == 'over_half' else fact.votes
    return None


def majority(value):
    return value == '>50' or (value is not None and value > 50)


def calculate(data):
    names = {x.id: x.name for x in [*data.companies, *data.persons]}
    decisions = {tuple(sorted((d.first, d.second))): d for d in data.decisions if d.as_of == data.as_of}
    grouped = defaultdict(list)
    pending = defaultdict(list)
    for fact in data.voting_facts:
        if active(fact, data.as_of):
            grouped[(fact.owner, fact.company)].append(fact)
        elif not fact.valid_from and fact.reviewed_as_of != data.as_of:
            pending[fact.company].append(fact)
    chosen = {}
    conflicts = set()
    priority = {'expert': 3, 'explicit': 2, 'ownership_default': 1, 'unknown': 0}
    for edge, facts in grouped.items():
        level = max(priority[f.vote_mode] for f in facts)
        best = [f for f in facts if priority[f.vote_mode] == level]
        if len({str(effective_vote(f)) for f in best}) > 1:
            conflicts.add(edge)
        else:
            chosen[edge] = best[0]

    graph = influence_graph(chosen, conflicts, list(names), [c.id for c in data.companies], names, effective_vote)
    families, family_limited, family_conflicts = family_groups(data, active)
    family_graph = influence_graph(chosen, conflicts, list(names), [c.id for c in data.companies], names,
                                   effective_vote, sources={f['id']: set(f['members']) for f in families}) if families else {}
    facts_by_id = {f.id: f for f in chosen.values()}
    rows = []
    for a, b in combinations(data.companies, 2):
        key = tuple(sorted((a.id, b.id)))
        d = decisions.get(key)
        signals, missing, used = [], [], []
        calculations = []
        dependencies = set()
        for owner in names:
            related_values = {}
            for target in (a.id, b.id):
                if owner == target:
                    continue
                value, fact_ids, errors = graph[(owner, target)]
                if owner not in (a.id, b.id) and not fact_ids and not errors:
                    continue
                dependencies.update(fact_ids)
                missing.extend(errors)
                if value and value.high > 0:
                    related_values[target] = value
                    if owner in (a.id, b.id) or value.majority:
                        calculations.append({'owner': owner, 'company': target,
                                             'value': value.label, 'majority': value.majority,
                                             'fact_ids': sorted(fact_ids),
                                             'basis': 'Ptk. 8:2. § (4)'})
                if owner in (a.id, b.id) and value and value.majority:
                    kind = 'Közvetlen' if len(fact_ids) == 1 else 'Közvetlen és/vagy közvetett'
                    signals.append(f'{kind} szavazati befolyás: {names[owner]} → {names[target]}: {value.label} (Ptk. 8:2. §).')
            if owner not in (a.id, b.id) and all(target in related_values and related_values[target].majority for target in (a.id, b.id)):
                signals.append(f'Közös közvetlen/közvetett többségi szavazati szereplő: {names[owner]} (Ptk. 8:2. §; Tao. 4. § 23. pont c)).')
        family_evidence = []
        for group in families:
            family_values, family_used, errors = {}, set(), []
            for target in (a.id, b.id):
                value, fact_ids, problems = family_graph[(group['id'], target)]
                family_used.update(fact_ids)
                errors.extend(problems)
                if value and value.high > 0:
                    family_values[target] = value
                    calculations.append({'owner': group['id'], 'owner_name': group['name'],
                                         'company': target, 'value': value.label, 'majority': value.majority,
                                         'fact_ids': sorted(fact_ids), 'members': group['members'],
                                         'basis': 'Ptk. 8:1. § (1) 1.; 8:2. § (4)–(5); Tao. 4. § 23. c)'})
            if family_used or errors:
                dependencies.update(family_used)
                missing.extend(errors)
                family_evidence.extend(group['facts'])
            if all(target in family_values and family_values[target].majority for target in (a.id, b.id)):
                signals.append(f'Igazolt közeli hozzátartozók összeszámított többségi szavazata: {group["name"]} → {a.name}: {family_values[a.id].label}; {b.name}: {family_values[b.id].label}.')
        for fact in data.family_facts:
            if fact.relationship in CLOSE_FAMILY_TYPES and not (fact.confirmed and active(fact, data.as_of)):
                # Historical ended/future relations are not outstanding current facts.
                if (fact.valid_to and fact.valid_to <= data.as_of) or (fact.valid_from and fact.valid_from > data.as_of):
                    continue
                if any(graph[(person, target)][1] or graph[(person, target)][2]
                       for person in (fact.first, fact.second) for target in (a.id, b.id)):
                    missing.append(f'{names[fact.first]} – {names[fact.second]}: a rokonság vagy vizsgálati napi fennállása nincs igazolva.')
        for first, second in family_conflicts:
            if any(graph[(person, target)][1] or graph[(person, target)][2]
                   for person in (first, second) for target in (a.id, b.id)):
                missing.append(f'{names[first]} – {names[second]}: eltérő igazolt rokonsági adatok; forrásellenőrzés szükséges.')
        if family_limited:
            missing.append('A rokonsági háló túl összetett; a teljes csoportosításhoz szakértői felülvizsgálat szükséges.')
        used = [facts_by_id[fid].model_dump(mode='json') for fid in sorted(dependencies)]
        for target in {facts_by_id[fid].company for fid in dependencies} - {a.id, b.id}:
            if pending[target]:
                missing.append(f'{names[target]}: a köztes cég hiányzó kezdőnapú tényét a vizsgálati napra ellenőrizni kell.')
        for cid in (a.id, b.id):
            if pending[cid]:
                missing.append(f'{names[cid]}: a hiányzó kezdőnapú tények vizsgálati napi fennállása nincs megerősítve.')
        unknown_owner = [f for (owner, target), f in chosen.items() if target in (a.id, b.id) and effective_vote(f) is None]
        if unknown_owner:
            missing.append('A tulajdonosi körben ismeretlen szavazati adat van.')
        if any(target in (a.id, b.id) for owner, target in conflicts):
            missing.append('A tulajdonosi körben forrásütközés van.')
        missing = list(dict.fromkeys(missing))
        result = 'undetermined'
        if d and d.confirmed:
            result = d.result
            stage = 'expert' if result != 'undetermined' else d.stage
        elif d and d.result != 'undetermined':
            stage = 'expert_draft'
        elif signals:
            stage = 'voting_signal'
        elif missing:
            stage = 'missing_data'
        elif d and d.stage != 'unreviewed':
            stage = d.stage
        elif all(c.registry_reviewed_on == data.as_of for c in (a, b)):
            stage = 'awaiting_declaration'
        else:
            stage = 'unreviewed'
        # A manual waiting label must never hide a concrete missing fact.
        if result == 'undetermined' and stage == 'awaiting_declaration' and (missing or signals):
            stage = 'voting_signal' if signals else 'missing_data'
        explanation = d.reason if d and d.reason else (
            'A feldolgozott cégjegyzéki adatokban kapcsoltságra utaló jel nem látható; célzott nyilatkozat szükséges.'
            if stage == 'awaiting_declaration' else
            'A jelzett szavazati adat jogi értékelése szakértői döntést igényel.' if signals else
            'Az iratok és a releváns jogalapok ellenőrzése szükséges.')
        assumptions = list(dict.fromkeys([
            *(f'{names[f["owner"]]} → {names[f["company"]]}: tulajdon = szavazat munkafeltételezés.' for f in used if f['vote_mode'] == 'ownership_default'),
            *([d.assumptions] if d and d.assumptions else []),
        ]))
        rows.append({
            'first': a.id, 'second': b.id, 'first_name': a.name, 'second_name': b.name,
            'result': result, 'label': RESULT_LABELS[result], 'stage': stage, 'stage_label': STAGE_LABELS[stage],
            'basis': d.basis if d else '', 'reason': explanation,
            'evidence': d.evidence.model_dump(mode='json') if d else {},
            'signals': signals, 'missing': [*missing, *([d.missing] if d and d.missing else [])],
            'assumptions': assumptions, 'facts': used, 'influence_calculations': calculations, 'family_facts': list({f['id']: f for f in family_evidence}.values()), 'confirmed': bool(d and d.confirmed),
        })
    counts = {value: sum(r['result'] == value for r in rows) for value in RESULT_LABELS}
    stages = {value: sum(r['stage'] == value for r in rows) for value in STAGE_LABELS}
    return {'rule_version': RULE_VERSION, 'as_of': data.as_of.isoformat(), 'rows': rows,
            'counts': counts, 'stages': stages, 'total_pairs': len(rows),
            'complete': counts['undetermined'] == 0,
            'law_profile_present': bool(data.law_date and data.law_source),
            'mode': 'expert_decisions',
            'note': 'A közvetlen és közvetett szavazati jelzések Ptk. 8:2. § szerinti számítások; a teljes Tao-jogi eredményt a szakértő rögzíti.'}
