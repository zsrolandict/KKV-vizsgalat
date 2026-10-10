"""Generate shareable opinions from wholly fictitious data; never uses the local database."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.models import Assessment
from app.engine import calculate
from app.reports import word_report
from app.tao_models import TaoAssessment
from app.tao_engine import calculate as tao_calculate
from app.tao_reports import word_report as tao_word_report
from app.pdf_export import convert

OUT=Path(__file__).resolve().parent.parent/'docs/peldak';OUT.mkdir(exist_ok=True)
meta={'id':'fiktiv-bemutato','version':1,'approved':False}
common={'client':'Fiktív bemutató megbízó','as_of':'2026-10-10','law_date':'2025-12-31',
        'law_source':'Fiktív mintahivatkozás; a példa nem igazol jogforrás-ellenőrzést.',
        'report_issuer':'Minta szakértői iroda','report_signatory':'Mintaszakértő','report_place':'Budapest',
        'assumptions':'A minta kizárólag kitalált adatokat tartalmaz. A megbízói számadatok teljességét a mintában feltételezzük.\n'
                      'A megállapítások a megadott vizsgálati időpontra vonatkoznak; más irányítási jogosultság hiányát nem következtetjük a tulajdoni arányból.',
        'market_analysis':'Fiktív tényállás: Alfa és Gamma ipari szolgáltatásokat nyújt ugyanazon földrajzi térségben. '
                          'A közös üzleti döntések és az azonos vevői kör értékelését a minta szakértői indoka rögzíti; valós ügyben szerződések és nyilatkozatok szükségesek.',
        'legal_references':[{'id':'r1','case_number':'C-110/13','title':'HaTeFo – kutatási kiindulópont',
             'url':'https://eur-lex.europa.eu/legal-content/HU/TXT/?uri=CELEX:62013CJ0110',
             'relevance':'Az eredeti döntés és a konkrét tényállási egyezések vizsgálata még szükséges.','checked':False}]}
companies=[{'id':x,'name':name} for x,name in [('a','Fiktív Alfa Kft.'),('b','Fiktív Béta Kft.'),('c','Fiktív Gamma Kft.')]]
raw={**common,'title':'Fiktív KKV-állásfoglalás bemutató','root':'a','years':[2024,2025],'companies':companies,
     'persons':[{'id':'p','name':'Fiktív tulajdonos'}],
     'ownerships':[{'id':'o','owner':'a','company':'b','capital':30,'votes':30,'source':'Fiktív társasági szerződés'},
                   {'id':'p-a','owner':'p','company':'a','capital':100,'votes':100,'source':'Fiktív nyilatkozat'},
                   {'id':'p-c','owner':'p','company':'c','capital':100,'votes':100,'source':'Fiktív nyilatkozat'}],
     'decisions':[{'id':'d','first':'a','second':'c','relation':'linked','basis':'persons','confirmed':True,
                   'reason':'Fiktív bemutató: dokumentált közös irányítás és azonos piac.',
                   'acting_together':'A mintában ugyanaz a személy hozza az üzleti döntéseket.',
                   'market':'Azonos ipari szolgáltatások, azonos földrajzi vevői kör – fiktív tényállás.',
                   'source':'Fiktív megbízói nyilatkozat'}],
     'financials':[{'company':c,'year':y,'employees':n,'turnover':t,'balance':b,
                   'start':f'{y}-01-01','end':f'{y}-12-31','accepted':f'{y+1}-05-31','source':'Fiktív bemutató beszámoló'}
         for y in [2024,2025] for c,n,t,b in [('a',50 if y==2025 else 45,1400000000,900000000),('b',25,500000000,400000000),('c',12,300000000,200000000)]],
     'rates':[{'year':y,'date':f'{y}-12-31','quoted':f'{y}-12-31','value':400,'source':'Fiktív bemutató árfolyam; nem MNB-adat','confirmed':True} for y in [2024,2025]]}
kkv=Assessment.model_validate(raw)
tao_raw={**common,'as_of':'2025-12-31','title':'Fiktív Tao-állásfoglalás bemutató','companies':companies,
         'scope':'A felsorolt három vállalkozás kapcsoltsága a rögzített napon. Fiktív mintavizsgálat.',
         'voting_facts':[{'id':'v','owner':'a','company':'b','capital':60,'vote_mode':'ownership_default','reviewed_as_of':'2025-12-31','evidence':{'source':'Fiktív társasági szerződés'}}],
         'decisions':[{'first':'a','second':'b','as_of':'2025-12-31','result':'related','confirmed':True,'legal_ground':'abc',
           'basis':'Tao. 4. § 23. a) – fiktív példában ellenőrzött jogalap','reason':'A fiktív társasági szerződés alapján Alfa többségi szavazati befolyása áll fenn Bétában. A mintában nincs eltérő szavazati kikötés.',
           'evidence':{'source':'Fiktív társasági szerződés és szavazati nyilatkozat'}},
           {'first':'b','second':'c','as_of':'2025-12-31','result':'not_related','confirmed':True,'relevant_grounds_reviewed':True,
            'basis':'Tao. 4. § 23. releváns jogalapjai – fiktív bemutató','reason':'A mintában a vállalt kör minden releváns kapcsoltsági jogalapját megvizsgáltuk; e cégpárnál kapcsoltság nem került megállapításra.',
            'evidence':{'source':'Fiktív tényállási nyilatkozat'}},
           {'first':'a','second':'c','as_of':'2025-12-31','result':'undetermined','confirmed':True,'stage':'awaiting_declaration',
            'reason':'Alfa és Gamma tényleges döntési rendjéről még nincs elegendő irat a fiktív mintában.',
            'missing':'Be kell kérni az irányítási jogosultságokat és a döntési rendet igazoló nyilatkozatot.'}]}
tao=TaoAssessment.model_validate(tao_raw)
for name,rawdoc in [('KKV_allasfoglalas_minta',word_report(kkv,calculate(kkv),meta)),
                    ('Tao_allasfoglalas_minta',tao_word_report(tao,tao_calculate(tao),{**meta,'label':'TERVEZET'}))]:
    path=OUT/(name+'.docx');path.write_bytes(rawdoc);convert(path,path.with_suffix('.pdf'));print(path.name)
