"""Ptk. 8:2(4) voting influence on acyclic, non-conflicting fact graphs.

An open lower bound preserves a documented >50 without inventing an exact vote.
Cycles and uncertain inputs remain unresolved, never a negative legal conclusion.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal, localcontext

ZERO = Decimal(0)
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class Range:
    low: Decimal
    high: Decimal
    open_low: bool = False

    @property
    def majority(self):
        return self.low > 50 or (self.low == 50 and self.open_low)

    @property
    def label(self):
        if self.low == self.high:
            return f'{self.low:f}%'
        if self.low == 50 and self.open_low and self.high == 100:
            return '>50%'
        return f'{self.low:f}–{self.high:f}%' + (' (alsó határ kizáró)' if self.open_low else '')


def influence_graph(chosen, conflicts, actors, companies, names, effective_vote, sources=None):
    """Return source/target contributions, dependencies and unresolved reasons."""
    incoming, outgoing = defaultdict(list), defaultdict(set)
    edges = set(chosen) | set(conflicts)
    for owner, target in sorted(edges):
        incoming[target].append(owner)
        outgoing[owner].add(target)
    indegree = {node: len(incoming[node]) for node in actors}
    queue = deque(node for node in actors if indegree[node] == 0)
    ordered = []
    while queue:
        node = queue.popleft()
        ordered.append(node)
        for target in sorted(outgoing[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    blocked = set(actors) - set(ordered)  # Cycle and everything depending on it.
    invalid = set()
    for target, owners in incoming.items():
        votes = [effective_vote(f) for owner in owners if (f := chosen.get((owner, target)))]
        minimum_total = sum((Decimal(50) if value == '>50' else value
                             for value in votes if value is not None), ZERO)
        if minimum_total > HUNDRED or (minimum_total == HUNDRED and '>50' in votes):
            invalid.add(target)
    results = {}
    with localcontext() as context:
        context.prec = 1000  # Long minority chains must not round up to the threshold.
        for source, roots in (sources or {actor: {actor} for actor in actors}).items():
            reachable, stack = set(), list(roots)
            while stack:
                for target in outgoing[stack.pop()]:
                    if target not in reachable:
                        reachable.add(target)
                        stack.append(target)
            values = {member: (Range(HUNDRED, HUNDRED), set(), []) for member in roots}
            for target in ordered:
                if target in roots or target not in reachable:
                    continue
                low, high, open_low, used, missing = ZERO, ZERO, False, set(), []
                for owner in incoming[target]:
                    if owner not in roots and owner not in reachable:
                        continue
                    edge = (owner, target)
                    fact = chosen.get(edge)
                    if edge in conflicts:
                        missing.append(f'Eltérő szavazati adatok: {names[owner]} → {names[target]}.')
                        continue
                    vote = effective_vote(fact)
                    used.add(fact.id)
                    if vote is None:
                        missing.append(f'Hiányzó szavazati arány: {names[owner]} → {names[target]}.')
                        continue
                    prior, dependencies, errors = values.get(owner, (None, set(), ['Körkörös tulajdonlás: szakértői számítás szükséges.']))
                    used.update(dependencies)
                    missing.extend(errors)
                    if prior is None:
                        continue
                    coefficient_low = HUNDRED if prior.majority else prior.low
                    coefficient_high = HUNDRED if prior.high > 50 else prior.high
                    contribution_low = coefficient_low * (Decimal(50) if vote == '>50' else vote) / HUNDRED
                    contribution_high = coefficient_high * (HUNDRED if vote == '>50' else vote) / HUNDRED
                    low += contribution_low
                    high += contribution_high
                    open_low |= contribution_low > 0 and (vote == '>50' or (prior.open_low and not prior.majority))
                if target in invalid or low > HUNDRED:
                    missing.append(f'{names[target]}: a szavazatok összege meghaladja a 100%-ot.')
                values[target] = (None if missing else Range(low, min(high, HUNDRED), open_low), used, list(dict.fromkeys(missing)))
            for target in companies:
                if target == source:
                    continue
                if target in reachable and target in blocked:
                    results[(source, target)] = (None, set(), ['Körkörös tulajdonlás vagy attól függő útvonal: szakértői számítás szükséges.'])
                else:
                    results[(source, target)] = values.get(target, (Range(ZERO, ZERO), set(), []))
    return results
