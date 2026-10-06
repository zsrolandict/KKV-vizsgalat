from datetime import date
from .models import Assessment


def demonstration():
    names = ['Minta Ipar Kft.', 'Minta Szállítás Kft.', 'Minta Építő Kft.',
             'Minta Logisztika Kft.', 'Minta Kereskedelem Kft.', 'Minta Fuvar Kft.',
             'Minta Motor Kft.', 'Minta Szolgáltató Kft.', 'Minta Projekt Kft.']
    values = {
      2024: [(81,1451643,1087768),(17,234876,40445),(34,2138368,1037823),
             (7,85319,47914),(2,0,2805),(5,439858,135077),(0,0,0),(4,70220,161642),(19,320318,107207)],
      2025: [(94,1662803,1247671),(16,255903,51427),(32,2236917,1161917),
             (7,102607,63489),(2,0,1313),(8,525685,373419),(0,0,0),(4,55304,158891),(20,436209,110550)]}
    percentages=[100,100,50,50,50,100,100,50,18]
    data={'title':'KKV-vizsgálat · mintacsoport','client':'Bemutató ügy',
          'purpose':'KKV-minősítés – az Excel példájának ellenőrzése','as_of':date.today().isoformat(),
          'root':'c1','years':[2024,2025], 'companies':[{'id':f'c{i+1}','name':n,'activity':'Bemutató adatok; tényleges tevékenység ellenőrzendő.'} for i,n in enumerate(names)],
          'persons':[{'id':f'p{i}','name':f'Tulajdonos {chr(64+i)}'} for i in range(1,7)],
          'ownerships':[], 'decisions':[], 'financials':[], 'rates':[],
          'assumptions':'Bemutató ügy a csatolt Excel számszerű adataiból. A cég- és személynevek mintanevek. A kapcsolati besorolások és árfolyamok szakértői ellenőrzést igényelnek.'}
    ownerships=[('p1','c1',90),('p2','c1',10),('p2','c2',100),('p3','c3',50),('p2','c3',50),
                ('p3','c4',50),('p1','c4',50),('p2','c5',50),('p4','c5',50),('p5','c6',100),
                ('p4','c7',100),('p1','c8',50),('p3','c8',25),('p6','c8',25),('p1','c9',18)]
    for i,(owner,company,pct) in enumerate(ownerships):
        data['ownerships'].append({'id':f'o{i}','owner':owner,'company':company,'capital':pct,'votes':pct,'source':'Excel mintája; ellenőrzendő'})
    for i,pct in enumerate(percentages[1:],start=2):
        rel='linked' if pct==100 else 'partner' if pct>=25 else 'independent'
        data['decisions'].append({'id':f'd{i}','first':'c1','second':f'c{i}',
            'relation':rel,'percent':pct if rel=='partner' else 0,'basis':'expert',
            'reason':'Az eredeti Excel kézi kapcsolati besorolása; jogi ellenőrzés szükséges.',
            'source':'KKV vizsgálat _vfin2.xlsx – befolyás oszlop','confirmed':False})
    for year, rows in values.items():
        for i,(employees,turnover,balance) in enumerate(rows):
            data['financials'].append({'company':f'c{i+1}','year':year,'employees':employees,
                'turnover':turnover*1000,'balance':balance*1000,
                'start':f'{year}-01-01','end':f'{year}-12-31','accepted':f'{year+1}-05-31',
                'source':'Csatolt Excel mintája – szakértőileg még nem ellenőrzött'})
        data['rates'].append({'year':year,'date':f'{year}-12-31',
            'value':'410.09' if year==2024 else '385.4',
            'source':'Az Excelben megadott érték; MNB-forrásellenőrzés szükséges.','confirmed':False})
    return Assessment.model_validate(data)
