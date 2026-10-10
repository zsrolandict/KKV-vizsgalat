"""Case-specific report prose. The attachment is a structural reference, not case data."""
from decimal import Decimal as D, localcontext
from .engine import LABELS, LIMITS, calculate

RELATIONS = {'own': 'Saját vállalkozás', 'linked': 'Kapcsolódó vállalkozás',
             'partner': 'Partnervállalkozás', 'independent': 'Önálló / nem beszámítandó',
             'unresolved': 'Tisztázandó kapcsolat', 'consolidated': 'Konszolidált adat',
             'scenario': '100%-os feltételezés'}


def hu(value, decimals=3):
    if value is None:
        return '–'
    with localcontext() as context:
        context.prec = 80
        result = f'{D(str(value)):,.{decimals}f}'.replace(',', '\u00a0').replace('.', ',')
    return result.rstrip('0').rstrip(',') if decimals else result


def money(value):
    if value is None:
        return '–'
    with localcontext() as context:
        context.prec = 80
        return hu(D(str(value)) / 1000)


def annual_reason(year):
    if not year['complete'] or year['category'] is None or not year['rate']:
        return 'A rendelkezésre álló adatok hiányosak; az éves méret megbízható megállapításához a hiányzó beszámoló- vagy árfolyamadatokat rendezni kell.'
    index = {'micro': 0, 'small': 1, 'medium': 2, 'large': 2}[year['category']]
    with localcontext() as context:
        context.prec = 80
        n, t, b = LIMITS[index]
        totals = year['totals']
        fx = D(year['rate'])
        employees = D(totals['employees'])
        turnover, balance = D(totals['turnover']), D(totals['balance'])
        staff_ok, turnover_ok, balance_ok = employees < n, turnover <= t*fx, balance <= b*fx
        name = ['mikrovállalkozási', 'kisvállalkozási', 'középvállalkozási'][index]
        staff = f'A {hu(employees)} fős összesített létszám a {hu(n, 0)} fő alatti feltételt {"teljesíti" if staff_ok else "nem teljesíti"}.'
        finance = (f'Az összesített árbevétel {money(turnover)} ezer Ft, a {money(t*fx)} ezer Ft-os határt '
                   f'{"nem haladja meg" if turnover_ok else "meghaladja"}; a mérlegfőösszeg {money(balance)} ezer Ft, '
                   f'a {money(b*fx)} ezer Ft-os határt {"nem haladja meg" if balance_ok else "meghaladja"}.')
        result = ('A létszámfeltétel és legalább az egyik pénzügyi feltétel teljesül.'
                  if staff_ok and (turnover_ok or balance_ok) else
                  'A létszámfeltétel és legalább az egyik pénzügyi feltétel együttes teljesülése nem igazolható.')
        smaller = []
        for key, (smaller_n, smaller_t, smaller_b) in zip(['mikro', 'kis'], LIMITS[:index]):
            why = 'a létszámhatár nem teljesül' if employees >= smaller_n else 'mindkét pénzügyi határérték túllépett'
            smaller.append(f'a {key} kategória nem alkalmazható, mert {why}')
        excluded = (' A kisebb kategóriák vizsgálata: '+ '; '.join(smaller)+'.') if smaller else ''
        return f'A {name} határ vizsgálata: {staff} {finance} {result}{excluded} Az éves méret: {year["label"]}.'


def report_summary(data, calculation, metadata):
    root = next(c for c in data.companies if c.id == data.root)
    draft = not metadata['approved']
    ready = calculation['ready'] and not calculation['blockers']
    if not ready:
        conclusion = (f'{root.name} végleges KKV-minősítése a jelenlegi adatokból még nem igazolható. '
                      f'A számítás előzetes eredménye: {calculation["label"]}. '
                      f'A végleges állásfoglalás előtt a dokumentumban felsorolt nyitott kérdéseket rendezni kell.')
    else:
        conclusion = (f'A dokumentált kapcsolati minősítés, az összesített gazdasági mutatók és a történeti szabály '
                      f'alkalmazása alapján {root.name} megállapított minősítése: {calculation["label"]}. '
                      + ('Ez szakértői jóváhagyásra váró következtetés.' if draft else
                         'A következtetés a jóváhagyott ügyverzióhoz és a rögzített vizsgálati időponthoz kötődik.'))
    opening = (f'A vizsgálat tárgya annak megállapítása, hogy {root.name} a rögzített jogi profil alapján '
               'a mikro-, kis- vagy középvállalkozási méretkategóriába tartozik-e, illetve fennáll-e a KKV-körből való kizárás. '
               f'A vizsgálat célja: {data.purpose}')
    annuals = [{'year': y['year'], 'label': y['label'], 'totals': y['totals'], 'closing': y['closing'],
                'complete': y['complete'], 'reason': annual_reason(y)} for y in calculation['years']]
    relationships = []
    for year in calculation['years']:
        for relation in ['linked', 'partner', 'independent', 'unresolved', 'consolidated']:
            rows = [r for r in year['rows'] if r['relation'] == relation]
            if not rows:
                continue
            names = '; '.join(f'{r["name"]} ({hu(r["percent"])}%)' for r in rows)
            prefix = { 'linked': 'Kapcsolódóként, teljes beszámítással figyelembe vett vállalkozások',
                       'partner': 'Arányosan figyelembe vett partner-adatblokkok',
                       'independent': 'Az adott évi összesítésben nem beszámított vállalkozások',
                       'unresolved': 'Még nem minősített vállalkozások; a 0%-os tétel nem igazolt kizárás',
                       'consolidated': 'A konszolidált beszámolóban már szereplő, külön nem összegzett vállalkozások'}[relation]
            relationships.append(f'{year["year"]}: {prefix}: {names}.')
    history = []
    for item in calculation['history']:
        history.append(f'{item["year"]}: az éves méret {LABELS.get(item["annual"], "hiányos adat")}; '
                       f'a történeti szabály szerinti állapot {LABELS.get(item["effective"], "további előzmény szükséges")}.'
                       + (' Eltérés megfigyelése folyamatban; az éves kategória nem azonos automatikusan a hatályos minősítéssel.' if item['pending'] else ''))
    sensitivity = None
    if len(data.companies) > 1:
        scenario = calculate(data, 'all')
        comparisons = []
        for base, full in zip(calculation['years'], scenario['years']):
            if not base['complete'] or not full['complete']:
                comparisons.append(f'{base["year"]}: hiányos számszerű adatok miatt a forgatókönyvek méretkategóriájának összehasonlítása nem véglegesíthető.')
            else:
                comparisons.append(f'{base["year"]}: az alapforgatókönyv éves mérete {base["label"]}; '
                                   f'minden aktív üzleti vállalkozás 100%-os beszámításával {full["label"]}. '
                                   + ('Az éves méretkategória nem változik.' if base['category'] == full['category'] else 'Az éves méretkategória megváltozik.'))
        sensitivity = {'years': scenario['years'], 'comparison': comparisons,
                       'explanation': 'A teljes összeszámítás érzékenységvizsgálat: minden, az adott hálóidőpontban aktív üzleti vállalkozást 100%-kal vesz figyelembe. Ez nem önálló jogi minősítés és nem bizonyítja az „egyetlen gazdasági egység” fennállását. Természetes személyeken keresztüli kapcsolódás esetén a közös fellépés és az azonos vagy szomszédos piac dokumentált tényállása külön szükséges.'}
    return {'company': root.name, 'approved': metadata['approved'], 'version': metadata['version'],
            'opening': opening, 'conclusion': conclusion, 'relationships': relationships,
            'annuals': annuals, 'history': history, 'sensitivity': sensitivity,
            'transfer_pricing': calculation['transfer_pricing'], 'blockers': calculation['blockers'],
            'purpose': data.purpose, 'as_of': data.as_of.isoformat(), 'notes': data.conclusion_notes}
