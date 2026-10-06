"""Deterministic Decimal calculation; uncertainty blocks final approval."""
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal as D, localcontext
from .models import Assessment

RULE_VERSION = 'KKV-2026.1-szakertoi'
CATEGORIES = ['micro', 'small', 'medium', 'large']
LABELS = {'micro': 'Mikrovállalkozás', 'small': 'Kisvállalkozás',
          'medium': 'Középvállalkozás', 'large': 'KKV-körön kívüli méret',
          'public': 'KKV-körön kívüli – közjogi részesedés', 'unknown': 'További előzmény szükséges'}
LIMITS = [(D(10), D(2000000), D(2000000)),
          (D(50), D(10000000), D(10000000)),
          (D(250), D(50000000), D(43000000))]


def text_decimal(value):
    raw = format(value, 'f')
    return raw.rstrip('0').rstrip('.') if '.' in raw else raw


def category(employees, turnover_huf, balance_huf, rate):
    for key, (n, t, b) in zip(CATEGORIES, LIMITS):
        if employees < n and (turnover_huf <= t * rate or balance_huf <= b * rate):
            return key
    return 'large'


def active(obj, day):
    return (not obj.start or obj.start <= day) and (not obj.end or day <= obj.end)


def transition(annuals, previous=None, immediate_years=None):
    """Confirm each nested size boundary independently after two equal observations."""
    immediate_years = immediate_years or set()
    flags = [CATEGORIES.index(previous) <= i for i in range(3)] if previous else [None]*3
    pending = [None]*3
    counts = [0]*3
    history = []
    last_year = None
    for year, annual in annuals:
        if last_year is not None and year != last_year + 1:
            pending, counts = [None]*3, [0]*3
        last_year = year
        if annual is None:
            pending, counts = [None]*3, [0]*3
            history.append({'year': year, 'annual': None, 'effective': None, 'pending': False})
            continue
        raw = [CATEGORIES.index(annual) <= i for i in range(3)]
        if year in immediate_years:
            flags, pending, counts = raw[:], [None]*3, [0]*3
        else:
            for i in range(3):
                if flags[i] is not None and raw[i] == flags[i]:
                    pending[i], counts[i] = None, 0
                else:
                    counts[i] = counts[i]+1 if pending[i] == raw[i] else 1
                    pending[i] = raw[i]
                    if counts[i] >= 2:
                        flags[i], pending[i], counts[i] = raw[i], None, 0
        effective = None
        # A smaller unknown boundary must not be silently skipped.
        for i, flag in enumerate(flags):
            if flag is None:
                break
            if flag:
                effective = CATEGORIES[i]
                break
        else:
            effective = 'large'
        history.append({'year': year, 'annual': annual, 'effective': effective,
                        'pending': any(p is not None for p in pending),
                        'boundaries': flags[:]})
    return history


def calculate(data: Assessment, scenario='base'):
    # Request workers and callers may have different Decimal contexts.
    with localcontext() as context:
        context.prec = 60
        return _calculate(data, scenario)


def _calculate(data: Assessment, scenario='base'):
    blockers, warnings = [], []
    companies = {c.id: c for c in data.companies}
    financials = {(f.company, f.year): f for f in data.financials}
    rates = {r.year: r for r in data.rates}
    years = sorted(data.years)
    results = []

    def issue(code, message, year=None):
        item = {'code': code, 'message': message, 'year': year}
        if item not in blockers:
            blockers.append(item)

    if not data.purpose:
        issue('purpose', 'Adja meg a vizsgálat célját.')
    if data.previous_category and (not data.previous_date or data.previous_date >= date(years[0], 1, 1)):
        issue('history_date', 'A korábbi minősítéshez a legelső vizsgált év előtti referenciaidőpont szükséges.')
    for event in data.events:
        if event.date > data.as_of:
            continue
        if not event.confirmed or not event.resolution:
            issue('event', f'Strukturális esemény szakértői rendezése szükséges: {event.description}')
    if scenario == 'all':
        warnings.append('Érzékenységvizsgálat: minden ismert üzleti vállalkozás 100%-os beszámítása. Nem önálló jogi minősítés.')

    for year in years:
        root_fin = financials.get((data.root, year))
        closing = root_fin.end if root_fin and root_fin.end else date(year, 12, 31)
        root_company = companies[data.root]
        structure_day = closing if data.structure_basis == 'period_end' else data.as_of
        if root_fin and root_fin.estimated and closing > data.as_of:
            structure_day = data.as_of
        rate = rates.get(year)
        if closing > data.as_of and not (root_fin and root_fin.estimated):
            issue('future_period', f'{year}: az üzleti év a vizsgálat időpontjában még nem zárult le.', year)
        expected_rate_day = date(year-1, 12, 31) if root_fin and root_fin.estimated else closing
        if not rate:
            issue('rate_missing', f'{year}: hiányzik a HUF/EUR árfolyam.', year)
            fx = None
        else:
            fx = rate.value
            if not rate.confirmed or not rate.source:
                issue('rate_unconfirmed', f'{year}: az árfolyam forrását és ellenőrzését rögzíteni kell.', year)
            if rate.date != expected_rate_day:
                issue('rate_date', f'{year}: az árfolyam érvényességi napja {expected_rate_day.isoformat()} legyen.', year)
            if rate.quoted and (rate.quoted > rate.date or (rate.date-rate.quoted).days > 10):
                issue('rate_quoted', f'{year}: a jegyzési nap nem megfelelő; MNB-forrásellenőrzés szükséges.', year)

        business = {i for i,c in companies.items() if c.kind != 'public'
                    and (not c.founded or c.founded <= structure_day)
                    and (not c.ceased or c.ceased >= structure_day)}
        if data.root not in business:
            issue('root_inactive', 'A vizsgált vállalkozás a kiválasztott hálóidőpontban még nem létezik vagy megszűnt.', year)
        linked = defaultdict(set)
        link_proofs = defaultdict(list)
        partners = []
        known = {data.root}
        ownership_sums = defaultdict(lambda: [D(0), D(0)])
        owners = [o for o in data.ownerships if active(o, structure_day)]
        for o in owners:
            totals = ownership_sums[o.company]
            totals[0] += o.capital; totals[1] += o.votes
            owner = companies.get(o.owner)
            if not o.source:
                issue('ownership_source', f'{companies[o.company].name}: tulajdoni kapcsolat forrása hiányzik.', year)
            if o.control and not o.reason:
                issue('control_reason', f'{companies[o.company].name}: az irányítási jog indoklása hiányzik.', year)
            if owner and owner.kind != 'public' and o.owner in business and o.company in business:
                known.update([o.owner, o.company])
                if o.votes > 50 or o.control:
                    linked[o.owner].add(o.company); linked[o.company].add(o.owner)
                    control_reason = o.reason if o.control else f'Többségi szavazat: {text_decimal(o.votes)}%'
                    link_proofs[tuple(sorted([o.owner,o.company]))].append(f'{owner.name} → {companies[o.company].name}: {control_reason}; forrás: {o.source or "hiányzik"}.')
                    known.update([o.owner, o.company])
                elif max(o.capital,o.votes) >= 25:
                    if owner.investor_exception:
                        if not owner.exception_reason:
                            issue('investor_reason', f'{owner.name}: befektetői kivétel indoklása hiányzik.', year)
                    else:
                        partners.append((o.owner,o.company,max(o.capital,o.votes),f'Tulajdon/szavazat: {o.source or "forrás nincs"}'))
                    known.update([o.owner, o.company])
        for cid, sums in ownership_sums.items():
            if any(s > 100 for s in sums):
                issue('ownership_sum', f'{companies[cid].name}: a tulajdoni vagy szavazati arányok összege meghaladja a 100%-ot.', year)

        for d in data.decisions:
            if not active(d, structure_day):
                continue
            if not d.confirmed or not d.reason or not d.source:
                issue('decision_review', f'Kapcsolati döntés ellenőrzése szükséges: {companies[d.first].name} – {companies[d.second].name}.', year)
            if d.basis == 'persons' and (not d.market or not d.acting_together):
                issue('persons_market', f'{companies[d.second].name}: a közös fellépés és a piaci kapcsolat indoklása szükséges.', year)
            if d.relation == 'unresolved':
                issue('relation_unresolved', f'Tisztázatlan kapcsolat: {companies[d.first].name} – {companies[d.second].name}.', year)
            elif d.relation == 'linked':
                linked[d.first].add(d.second); linked[d.second].add(d.first)
                link_proofs[tuple(sorted([d.first,d.second]))].append(f'{companies[d.first].name} ↔ {companies[d.second].name}: {d.reason or "indoklás hiányzik"}; forrás: {d.source or "hiányzik"}.')
            elif d.relation == 'partner':
                partners.append((d.first,d.second,d.percent,f'{d.reason}; forrás: {d.source or "hiányzik"}.'))
            known.update([d.first,d.second])

        components, visited = [], set()
        for cid in business:
            if cid in visited:
                continue
            group = set(); todo = [cid]
            while todo:
                node = todo.pop()
                if node in group or node not in business:
                    continue
                group.add(node); todo.extend(linked[node]-group)
            visited |= group; components.append(group)
        group_by_id = {cid:idx for idx,g in enumerate(components) for cid in g}
        root_group = group_by_id.get(data.root)
        weights = {cid:D(0) for cid in business}
        reasons = {cid:'Nincs beszámítható vállalkozási kapcsolat.' for cid in business}
        root_set = components[root_group] if root_group is not None else {data.root}
        routes = {data.root: []}
        queue = deque([data.root])
        while queue:
            node = queue.popleft()
            for neighbor in sorted(linked[node]):
                if neighbor in business and neighbor not in routes:
                    proof = ' '.join(link_proofs[tuple(sorted([node,neighbor]))])
                    routes[neighbor] = routes[node] + [proof]
                    queue.append(neighbor)
        for cid in root_set:
            weights[cid] = D(100)
            reasons[cid] = 'Saját vállalkozás.' if cid == data.root else '100%-os beszámítás. ' + ' '.join(routes.get(cid,[]))
        candidate_groups = defaultdict(list)
        seen_pairs = {}
        for a,b,w,why in partners:
            if a not in group_by_id or b not in group_by_id:
                continue
            ga,gb = group_by_id[a],group_by_id[b]
            if ga == gb:
                continue
            if ga == root_group or gb == root_group:
                other = gb if ga == root_group else ga
                key = tuple(sorted([a,b]))
                if key in seen_pairs:
                    if seen_pairs[key] != w:
                        issue('partner_conflict', 'Ugyanahhoz a cégpárhoz eltérő partnerarány tartozik.', year)
                    continue
                seen_pairs[key] = w
                candidate_groups[other].append((w,why))
        for gi, candidates in candidate_groups.items():
            group = components[gi]
            overrides = [o for o in data.overrides if o.year==year and o.company in group]
            if len(overrides)>1:
                issue('override_conflict','Egy kapcsolódó cégblokkhoz csak egy összeszámítási felülbírálat adható.',year)
            if overrides:
                o=overrides[0]; w=o.percent; why=o.reason
                if not o.confirmed:
                    issue('override_review','Összeszámítási felülbírálat jóváhagyása szükséges.',year)
            elif len(candidates)>1:
                issue('multiple_paths', f'Több partnerútvonal: {", ".join(companies[c].name for c in sorted(group))}. A blokk arányát szakértői összeszámítási döntéssel kell rögzíteni.',year)
                w=D(0);why='Több partnerútvonal – az arány még nincs megállapítva.'
            else:
                w,why=candidates[0]
            for cid in group:
                weights[cid]=w;reasons[cid]=f'Partner és kapcsolódó adatblokk: {why}'

        for d in data.decisions:
            if d.relation == 'independent' and active(d,structure_day):
                excluded_id = d.second if d.first == data.root else d.first if d.second == data.root else None
                if excluded_id in reasons and weights.get(excluded_id,0)==0:
                    reasons[excluded_id] = f'{d.reason}; forrás: {d.source or "hiányzik"}.'
                if d.first in group_by_id and d.second in group_by_id and group_by_id[d.first]==group_by_id[d.second]:
                    issue('independent_conflict','Az önálló minősítés ellentmond a kapcsolódási láncnak.',year)
                elif (d.first == data.root and weights.get(d.second,0)>0) or (d.second == data.root and weights.get(d.first,0)>0):
                    issue('independent_conflict','Az önálló minősítés ellentmond a releváns partnerbeszámításnak.',year)
        for cid in business:
            if cid not in known and scenario=='base':
                issue('relationship_missing',f'{companies[cid].name}: a kapcsolat vagy a kizárás indokát rögzíteni kell.',year)
        if scenario=='all':
            weights={cid:D(100) for cid in business}
            reasons={cid:'100%-os érzékenységvizsgálat.' for cid in business}

        covered={}
        for cid in sorted(business, key=lambda i:(i!=data.root,i)):
            f=financials.get((cid,year))
            if not f or not f.consolidated or weights[cid]==0:
                continue
            for included in f.included:
                if included == cid:
                    continue
                if included not in weights or weights[included]!=weights[cid]:
                    issue('consolidation_weight',f'{companies[cid].name}: eltérő súlyú konszolidáció szakértői rendezést igényel.',year)
                elif included in covered or cid in covered:
                    issue('consolidation_overlap','Átfedő konszolidált beszámolók: a források körét rendezni kell.',year)
                else:
                    covered[included]=cid

        rows=[];totals=[D(0),D(0),D(0)];numeric_complete=True
        for cid in sorted(business,key=lambda i:(i!=data.root,companies[i].name)):
            f=financials.get((cid,year));w=weights[cid]
            row={'company':cid,'name':companies[cid].name,'percent':text_decimal(w),
                 'relation':'own' if cid==data.root else 'scenario' if scenario=='all' else 'linked' if cid in root_set else 'partner' if w>0 else 'independent',
                 'reason':reasons[cid], 'included':False,'employees':None,'turnover':None,'balance':None,
                 'raw_employees':text_decimal(f.employees) if f and f.employees is not None else None,
                 'raw_turnover':text_decimal(f.turnover) if f and f.turnover is not None else None,
                 'raw_balance':text_decimal(f.balance) if f and f.balance is not None else None}
            if cid in covered:
                row['reason']=f'Adat már szerepel {companies[covered[cid]].name} konszolidált beszámolójában.'
                row['relation']='consolidated'
            elif w>0:
                if not f or any(v is None for v in (f.employees,f.turnover,f.balance)):
                    issue('financial_missing',f'{year}: {companies[cid].name} beszámolóadata hiányos.',year);numeric_complete=False
                elif f.currency=='EUR' and fx is None:
                    numeric_complete=False
                else:
                    if not f.source:
                        issue('financial_source',f'{year}: {companies[cid].name} adatforrása hiányzik.',year)
                    if not f.start or not f.end:
                        issue('financial_period',f'{year}: {companies[cid].name} beszámolási időszakát rögzíteni kell.',year)
                    if not f.estimated and (not f.accepted or f.accepted>data.as_of):
                        issue('financial_acceptance',f'{year}: {companies[cid].name} elfogadott beszámolója szükséges.',year)
                    if f.estimated and (not f.annualized or not f.source):
                        issue('estimate',f'{year}: {companies[cid].name} évesített becslésének indoklása szükséges.',year)
                    if f.start and f.end and (f.end-f.start).days<330 and not f.annualized:
                        issue('short_year',f'{year}: {companies[cid].name} rövid időszakának évesítése tisztázandó.',year)
                    if data.profile=='EU' and f.employment_method!='AWU':
                        issue('employment_method',f'{year}: EU-profilhoz {companies[cid].name} éves munkaegységben (AWU) mért létszáma szükséges.',year)
                    if f.end and f.end!=closing:
                        issue('period_alignment',f'{year}: eltérő üzletiév-zárás; {companies[cid].name} időszakát egyeztetni kell.',year)
                    money_fx=fx if f.currency=='EUR' else D(1)
                    values=[f.employees*w/100,f.turnover*money_fx*w/100,f.balance*money_fx*w/100]
                    totals=[t+v for t,v in zip(totals,values)]
                    row.update(dict(zip(['employees','turnover','balance'],map(text_decimal,values))));row['included']=True
            rows.append(row)

        public_owners=[o for o in owners if companies.get(o.owner) and companies[o.owner].kind=='public']
        direct=[o for o in public_owners if o.company==data.root]
        public_capital=sum((o.capital for o in direct),D(0))
        public_votes=sum((o.votes for o in direct),D(0))
        pr=data.public_review
        if public_owners or pr.capital > 0 or pr.votes > 0 or pr.exception:
            if not pr.confirmed or not pr.reason:
                issue('public_review','A közvetlen/közvetett közjogi részesedés összesített vizsgálata szükséges.',year)
            if pr.confirmed and (pr.capital<public_capital or pr.votes<public_votes):
                issue('public_conflict','A közjogi összesítés kisebb a rögzített közvetlen részesedésnél.',year)
        if pr.confirmed:
            public_capital=max(public_capital,pr.capital);public_votes=max(public_votes,pr.votes)
        excluded=(max(public_capital,public_votes)>25 if data.profile=='HU' else max(public_capital,public_votes)>=25)
        if pr.exception:
            if not pr.confirmed or not pr.reason:
                issue('public_exception','A közjogi kivétel szakértői indoklása hiányzik.',year)
            else:excluded=False
        annual=category(*totals,fx) if numeric_complete and fx is not None else None
        results.append({'year':year,'closing':closing.isoformat(),'rate':text_decimal(fx) if fx else None,
                        'totals':dict(zip(['employees','turnover','balance'],map(text_decimal,totals))),
                        'category':annual,'label':LABELS.get(annual,'Hiányos adat'),
                        'public_excluded':excluded,'rows':rows,'complete':numeric_complete and fx is not None})

    immediates={e.date.year for e in data.events if e.confirmed and e.immediate and e.resolution and e.date<=data.as_of}
    # An immediate event after the last closing still affects the latest assessment.
    if results and any(e.confirmed and e.immediate and e.resolution and date.fromisoformat(results[-1]['closing'])<e.date<=data.as_of for e in data.events):
        immediates.add(results[-1]['year'])
        if data.structure_basis != 'assessment':
            issue('post_event_structure', 'A zárást követő azonnali strukturális változáshoz a vizsgálati napi céghálót kell választani.')
    history=transition([(r['year'],r['category']) for r in results],data.previous_category,immediates)
    final=history[-1]['effective'] if history else None
    if not final:
        issue('history_unknown','A kétéves szabályhoz további előzmény vagy korábbi minősítés szükséges.')
    if results and results[-1]['public_excluded']:
        final='public'
    if scenario!='base':
        final=results[-1]['category'] if results else None
    return {'rule_version':RULE_VERSION,'scenario':scenario,'years':results,'history':history,
            'category':final,'label':LABELS.get(final,'További előzmény szükséges'),
            'blockers':blockers,'warnings':warnings,'ready':not blockers and scenario=='base',
            'transfer_pricing':('A kisvállalkozási minősítéshez kötött személyi mentesség nem állapítható meg; a konkrét kötelezettséghez kapcsoltügylet- és mentességvizsgálat szükséges.'
                if final in ['medium','large','public'] else 'A méret alapján kisvállalkozási személyi mentesség vizsgálható; az alkalmazandó adóévi feltételeket külön ellenőrizni kell.' if final else 'A minősítés tisztázásáig transzferár-következtetés nem véglegesíthető.')}
