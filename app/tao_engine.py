"""Deterministic fact signals and expert decisions; no unverified legal inference.

This first milestone does not implement the statutory indirect/family/BVK engine.
Voting signals are not automatically converted to legal related-party results.
"""
from collections import defaultdict
from itertools import combinations

RULE_VERSION = 'TAO-munkafolyamat-1.0-szakertoi-dontes'
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

    rows = []
    for a, b in combinations(data.companies, 2):
        key = tuple(sorted((a.id, b.id)))
        d = decisions.get(key)
        signals, missing, used = [], [], []
        owners_a = {owner for owner, target in chosen if target == a.id}
        owners_b = {owner for owner, target in chosen if target == b.id}
        relevant = {(a.id, b.id), (b.id, a.id)}
        relevant |= {(owner, target) for owner in owners_a & owners_b for target in (a.id, b.id)}
        for edge in relevant:
            if edge in conflicts:
                missing.append(f'Eltérő szavazati adatok: {names[edge[0]]} → {names[edge[1]]}.')
            fact = chosen.get(edge)
            if not fact:
                continue
            value = effective_vote(fact)
            used.append(fact.model_dump(mode='json'))
            if value is None:
                missing.append(f'Hiányzó szavazati arány: {names[edge[0]]} → {names[edge[1]]}.')
            elif majority(value) and edge[0] in (a.id, b.id):
                signals.append(f'{names[edge[0]]} → {names[edge[1]]}: {value}% szavazat.' if value != '>50' else f'{names[edge[0]]} → {names[edge[1]]}: szavazat >50%.')
        for owner in owners_a & owners_b:
            if majority(effective_vote(chosen[(owner, a.id)])) and majority(effective_vote(chosen[(owner, b.id)])):
                signals.append(f'Közös többségi szavazati szereplő: {names[owner]}.')
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
            'assumptions': assumptions, 'facts': used, 'confirmed': bool(d and d.confirmed),
        })
    counts = {value: sum(r['result'] == value for r in rows) for value in RESULT_LABELS}
    stages = {value: sum(r['stage'] == value for r in rows) for value in STAGE_LABELS}
    return {'rule_version': RULE_VERSION, 'as_of': data.as_of.isoformat(), 'rows': rows,
            'counts': counts, 'stages': stages, 'total_pairs': len(rows),
            'complete': counts['undetermined'] == 0,
            'law_profile_present': bool(data.law_date and data.law_source),
            'mode': 'expert_decisions',
            'note': 'A szavazati jelzések nem automatikus Tao-minősítések. A jogi eredményt a szakértő rögzíti.'}
