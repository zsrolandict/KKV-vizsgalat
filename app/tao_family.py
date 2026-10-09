"""Verified pairwise close relatives: never take a transitive family closure."""
from itertools import combinations
from .tao_models import CLOSE_FAMILY_TYPES


def family_groups(data, active):
    evidence = {}
    active_pairs = {}
    for fact in data.family_facts:
        if fact.confirmed and active(fact, data.as_of):
            active_pairs.setdefault(tuple(sorted((fact.first, fact.second))), []).append(fact)
    conflicts = {pair: facts for pair, facts in active_pairs.items() if len({f.relationship for f in facts}) > 1}
    neighbours = {p.id: set() for p in data.persons}
    for fact in data.family_facts:
        if fact.confirmed and fact.relationship in CLOSE_FAMILY_TYPES and active(fact, data.as_of):
            key = tuple(sorted((fact.first, fact.second)))
            if key in conflicts:
                continue
            evidence.setdefault(key, []).append(fact)
            neighbours[fact.first].add(fact.second)
            neighbours[fact.second].add(fact.first)
    # Maximal cliques contain only pairs explicitly proved to be close relatives.
    # Bounded search: an unusually complex family graph remains an expert task.
    cliques, steps = [], 0
    limited = False
    def visit(members, candidates, excluded):
        nonlocal steps, limited
        steps += 1
        if steps > 10000 or len(cliques) >= 250:
            limited = True
            return
        if not candidates and not excluded:
            if len(members) > 1:
                cliques.append(sorted(members))
            return
        pivot = max(sorted(candidates | excluded), key=lambda p: len(candidates & neighbours[p]), default=None)
        for person in sorted(candidates - (neighbours[pivot] if pivot else set())):
            visit(members | {person}, candidates & neighbours[person], excluded & neighbours[person])
            candidates.remove(person)
            excluded.add(person)
            if limited:
                return
    visit(set(), set(neighbours), set())
    names = {p.id: p.name for p in data.persons}
    groups = []
    identifiers = {p.id for p in [*data.companies, *data.persons]}
    for index, members in enumerate(sorted(cliques)):
        facts = [f for pair in combinations(members, 2) for f in evidence[tuple(sorted(pair))]]
        gid = f'family-group-{index}'
        while gid in identifiers:
            gid = '_' + gid
        identifiers.add(gid)
        groups.append({'id': gid, 'members': members,
                       'name': ' + '.join(names[p] for p in members),
                       'facts': [f.model_dump(mode='json') for f in facts]})
    return groups, limited, conflicts
