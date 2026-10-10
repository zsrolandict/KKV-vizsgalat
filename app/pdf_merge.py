"""Deterministic, opt-in import proposals. Facts and financial rows stay atomic."""
import copy
import hashlib
import json
import re
from uuid import NAMESPACE_URL, uuid5
from .models import Assessment
from .tao_models import TaoAssessment


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def registration(value):
    return re.sub(r'[^0-9A-Za-z]', '', value or '').casefold()


def proposals(existing, incoming, module, namespace, matches):
    current = copy.deepcopy(existing)
    source = incoming.model_dump(mode='json') if hasattr(incoming, 'model_dump') else copy.deepcopy(incoming)
    mapping, entities, operations = {}, [], []
    all_ids = {c['id'] for coll in ('companies','persons') for c in current.get(coll, [])}
    allowed = {c['id'] for coll in ('companies','persons') for c in source.get(coll, [])}
    if any(k not in allowed for k in matches):
        raise ValueError('Ismeretlen importszereplőhöz adott azonossági döntés.')
    def uid(value):
        return str(uuid5(NAMESPACE_URL, namespace + ':' + value))
    def add(collection, old, new, label):
        changes = [{'field': k, 'before': (old or {}).get(k), 'after': v} for k,v in new.items()
                   if k != 'id' and (old or {}).get(k) != v]
        if not changes:
            return
        op = dict(collection=collection, old=old, new=new, label=label, changes=changes)
        op['id'] = digest(op)
        if not any(o['id'] == op['id'] for o in operations):
            operations.append(op)
    for coll in ('companies','persons'):
        for actor in source.get(coll, []):
            target = None
            if actor['id'] in matches and matches[actor['id']]:
                target = next((a for a in current.get(coll, []) if a['id']==matches[actor['id']]),None)
                if not target:
                    raise ValueError('Az azonossági döntés eltérő vagy ismeretlen szereplőtípusra mutat.')
                if coll == 'companies' and registration(actor.get('registration')) and registration(target.get('registration')) and registration(actor.get('registration')) != registration(target.get('registration')):
                    raise ValueError('Eltérő cégazonosítókat nem lehet automatikusan összevonni. Javítsa vagy külön szereplőként rögzítse.')
            elif actor['id'] not in matches and coll == 'companies' and registration(actor.get('registration')):
                candidates = [a for a in current.get(coll, []) if registration(a.get('registration'))==registration(actor.get('registration'))]
                if len(candidates)==1:
                    target=candidates[0]
            new_id = target['id'] if target else actor['id'] if actor['id'] not in all_ids else uid('entity:'+actor['id'])
            mapping[actor['id']] = new_id
            entities.append(dict(id=actor['id'], name=actor['name'], collection=coll, matched_id=target['id'] if target else '',
                                 choices=[dict(id=a['id'],name=a['name']) for a in current.get(coll, [])]))
            if target:
                updated=copy.deepcopy(target)
                # Imported defaults must never overwrite expert metadata or organization type.
                for key in ('name','registration') if coll=='companies' else ('name',):
                    if actor.get(key):updated[key]=actor[key]
                add(coll,target,updated,actor['name'])
            else:
                add(coll,None,{**actor,'id':new_id},actor['name']+' – új szereplő')
    remapped=copy.deepcopy(source)
    for coll in ('voting_facts','ownerships','financials'):
        for item in remapped.get(coll, []):
            for key in ('owner','company'):
                if key in item:item[key]=mapping[item[key]]
    actor_names={mapping[a['id']]:a['name'] for coll in ('companies','persons') for a in source.get(coll,[])}
    fact_coll='voting_facts' if module=='tao' else 'ownerships'
    for index,fact in enumerate(remapped.get(fact_coll, [])):
        fact['id']=uid(fact_coll+':'+str(index))
        start_key='valid_from' if module=='tao' else 'start'
        candidates=[f for f in current.get(fact_coll, []) if all(f.get(k)==fact.get(k) for k in ('owner','company',start_key))]
        label=actor_names[fact['owner']]+' → '+actor_names[fact['company']]
        # Never downgrade or replace an expert vote, even when the imported row shares its key.
        editable=[f for f in candidates if f.get('vote_mode')!='expert' and not f.get('control')]
        old=editable[0] if len(editable)==1 and len(candidates)==1 else None
        if old:
            updated={**old,**fact,'id':old['id']}
            if module=='tao':updated['attribution_reviewed']=False
            add(fact_coll,old,updated,label)
        else:
            # Equivalent source facts need not be duplicated; changed/new sources remain explicit proposals.
            comparison=lambda f:{k:v for k,v in f.items() if k not in ('id','evidence','source')}
            if not any(comparison(f)==comparison(fact) for f in candidates):
                add(fact_coll,None,fact,label+(' – külön forrástény, szakértői felülbírálat megőrzésével' if candidates else ' – új tény'))
    if module=='kkv':
        for fact in remapped.get('financials', []):
            old=next((f for f in current['financials'] if (f['company'],f['year'])==(fact['company'],fact['year'])),None)
            if old and (old.get('currency') != fact.get('currency') or old.get('consolidated')):
                updated=fact
            else:
                updated={**(old or {}),**{k:v for k,v in fact.items() if v is not None}}
                if old and fact.get('employees') is None:
                    updated['employment_method']=old['employment_method']
                if old and any(fact.get(k) is None and old.get(k) is not None for k in ('employees','turnover','balance')):
                    updated['source'] = 'Megőrzött adat forrása: '+old.get('source','')+'; új adat forrása: '+fact.get('source','')
            if old and all(updated.get(k)==old.get(k) for k in ('employees','turnover','balance','start','end','currency')):
                continue
            updated.update(accepted=None,consolidated=False,included=[],estimated=False,annualized=False)
            add('financials',old,updated,actor_names[fact['company']]+' · '+str(fact['year'])+' – egyedi beszámolósor, újraellenőrzendő')
        years=sorted(set(current['years']) | {f['year'] for f in remapped.get('financials',[])})
        if years != current['years']:
            add('years',{'value':current['years']},{'value':years},'Vizsgált évek bővítése')
    token=digest(dict(existing=current,source=source,matches=matches,namespace=namespace,operations=operations))
    return dict(token=token,entities=entities,operations=operations)


def merge(existing, preview, selected, module):
    if len(selected)!=len(set(selected)) or set(selected)-{o['id'] for o in preview['operations']}:
        raise ValueError('Ismeretlen vagy ismételt módosításjelölés.')
    result=copy.deepcopy(existing)
    replacements = set()
    for operation in preview['operations']:
        if operation['id'] not in selected:continue
        coll=operation['collection'];old=operation['old'];new=operation['new']
        if coll=='years':result['years']=new['value'];continue
        if old is not None:
            replacement=(coll,str((old['company'],old['year']) if coll=='financials' else old.get('id')))
            if replacement in replacements:raise ValueError('Ugyanahhoz a korábbi adatsorhoz több eltérő javaslatot jelölt ki. Válasszon egy forrást.')
            replacements.add(replacement)
        if old is None:result.setdefault(coll,[]).append(new)
        else:
            key=lambda x:(x['company'],x['year']) if coll=='financials' else x['id']
            index=next(i for i,x in enumerate(result[coll]) if key(x)==key(old))
            result[coll][index]=new
    # A source update always creates a draft. Factual overrides survive; legal confirmations are renewed.
    for coll in ('decisions','overrides','events','family_facts','control_facts','management_facts','establishment_facts','trust_facts'):
        for fact in result.get(coll,[]):
            if 'confirmed' in fact:fact['confirmed']=False
    if module=='tao':
        for company in result['companies']:company['registry_reviewed_on']=None
        for fact in result['voting_facts']:
            if fact.get('capacity','own')!='own':fact['attribution_reviewed']=False
        return TaoAssessment.model_validate(result)
    for fact in result.get('financials',[]):
        if fact['year'] not in result['years']:
            raise ValueError('Az új pénzügyi sorhoz a vizsgált év bővítését is jelölje ki.')
    return Assessment.model_validate(result)
