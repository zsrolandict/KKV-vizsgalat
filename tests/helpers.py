from datetime import date
from app.models import Assessment


def sample():
    return Assessment.model_validate({
      'title':'Tesztvizsgálat','client':'Teszt ügyfél','as_of':'2026-10-06',
      'law_date':'2026-10-06','law_source':'Fiktív ellenőrzött jogi tesztforrás, 2024/2025-ös adatok alkalmazása ellenőrizve',
      'root':'a','years':[2024,2025],
      'companies':[{'id':'a','name':'Alfa Kft.'}],
      'financials':[{'company':'a','year':y,'employees':'2','turnover':'1000000','balance':'2000000',
         'start':f'{y}-01-01','end':f'{y}-12-31','accepted':f'{y+1}-05-31','source':'Ellenőrzött beszámoló'} for y in [2024,2025]],
      'rates':[{'year':y,'date':f'{y}-12-31','quoted':f'{y}-12-31','value':'400','source':'MNB – tesztadat','confirmed':True} for y in [2024,2025]]})


def extended(companies,edges):
    d=sample().model_dump(mode='json')
    for cid in companies:
        d['companies'].append({'id':cid,'name':cid.upper()+' Kft.'})
        d['financials'] += [{'company':cid,'year':y,'employees':'10','turnover':'10000000','balance':'5000000',
            'start':f'{y}-01-01','end':f'{y}-12-31','accepted':f'{y+1}-05-31','source':'Ellenőrzött beszámoló'} for y in [2024,2025]]
    for i,(a,b,pct) in enumerate(edges):
        d['ownerships'].append({'id':f'o{i}','owner':a,'company':b,'capital':str(pct),'votes':str(pct),'source':'Okirat'})
    return Assessment.model_validate(d)
