"""Evidence-backed controlling rights and pair-specific management signals."""
from collections import defaultdict, deque


def current_or_pending(fact, day):
    return not ((fact.valid_from and fact.valid_from > day) or (fact.valid_to and fact.valid_to <= day))


def qualifies(fact):
    if fact.membership == 'not_member' or fact.condition == 'no':
        return False
    if fact.membership != 'member' or fact.condition != 'yes':
        return None
    if fact.kind == 'voting_agreement':
        if fact.aligned_bound == 'over_half':
            return True
        return None if fact.aligned_votes is None else fact.aligned_votes > 50
    return True


def control_paths(data, graph, active):
    """Traverse only proved majority/control links, retaining their source records.

    Management alone is never propagated. Minority/rights mixed aggregation stays
    an explicit expert task; no synthetic percentage is created for a right.
    """
    names = {x.id: x.name for x in [*data.companies, *data.persons]}
    links, groups, pending = {}, defaultdict(list), []
    for (owner, target), (value, used, errors) in graph.items():
        if value and value.majority and not errors:
            links[(owner, target)] = {'votes': set(used), 'controls': set()}
    for fact in data.control_facts:
        if fact.confirmed and active(fact, data.as_of):
            groups[(fact.owner, fact.company, fact.kind)].append(fact)
        elif current_or_pending(fact, data.as_of):
            pending.append((fact, 'Az irányítási tény vagy vizsgálati napi fennállása nincs igazolva.'))
    for (owner, target, kind), facts in groups.items():
        states = {qualifies(f) for f in facts}
        if len(states) > 1:
            pending.extend((f, 'Eltérő igazolt irányítási források; felülvizsgálat szükséges.') for f in facts)
        elif states == {True}:
            link = links.setdefault((owner, target), {'votes': set(), 'controls': set()})
            link['controls'].update(f.id for f in facts)
        elif states == {None}:
            pending.extend((f, 'A tagi jogállás, irányítási feltétel vagy közös szavazati arány tisztázandó.') for f in facts)
    outgoing = defaultdict(list)
    for owner, target in sorted(links):
        outgoing[owner].append(target)
    paths = {}
    for source in names:
        queue = deque([(source, [source], set(), set())])
        visited = {(source, False)}
        while queue:
            owner, route, votes, controls = queue.popleft()
            for target in outgoing[owner]:
                link = links[(owner, target)]
                next_votes = votes | link['votes']
                next_controls = controls | link['controls']
                if target == source or target in route:
                    continue
                # Keep a right-bearing route even if a voting-only route also exists.
                key = (source, target)
                if next_controls and (key not in paths or not paths[key]['controls']):
                    paths[key] = {'route': [*route, target], 'votes': next_votes, 'controls': next_controls}
                marker = (target, bool(next_controls))
                if marker not in visited:
                    visited.add(marker)
                    queue.append((target, [*route, target], next_votes, next_controls))
    return paths, pending


def management_signals(data, first, second, active):
    key = {first, second}
    facts = [f for f in data.management_facts if {f.first, f.second} == key and current_or_pending(f, data.as_of)]
    verified = [f for f in facts if f.confirmed and active(f, data.as_of)]
    signatures = {(f.common_management, f.business_control, f.financial_control) for f in verified}
    missing, signals = [], []
    if len(signatures) > 1:
        missing.append('Eltérő igazolt ügyvezetési/irányítási források; felülvizsgálat szükséges.')
    elif verified:
        fact = verified[0]
        conditions = (fact.common_management, fact.business_control, fact.financial_control)
        if all(v == 'yes' for v in conditions):
            signals.append('Igazolt ügyvezetési egyezőség és döntő befolyás az üzleti ÉS pénzügyi politikában (Tao. 4. § 23. f)).')
        elif 'no' not in conditions:
            missing.append('Az ügyvezetési egyezőségből eredő üzleti és pénzügyi döntő befolyás tisztázandó.')
    if len(verified) != len(facts):
        missing.append('Az ügyvezetési tény vagy vizsgálati napi fennállása nincs igazolva.')
    return signals, missing, [f.model_dump(mode='json') for f in facts]
