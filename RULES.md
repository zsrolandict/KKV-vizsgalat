# Számítási szabálykönyv – első megvalósítás

Szabályverzió: `KKV-2026.1-szakertoi`. Az alkalmazandó jogi időállapotot és az ügyre való alkalmazhatóságot a jóváhagyó szakértő külön igazolja. A szabályverzió technikai azonosító, nem hivatalos jogi hitelesítés.

## Numerikus méret

| Kategória | Létszám | Árbevétel EUR | Mérleg EUR |
|---|---|---|---|
| Mikro | < 10 | ≤ 2 000 000 | ≤ 2 000 000 |
| Kis | < 50 | ≤ 10 000 000 | ≤ 10 000 000 |
| Közép | < 250 | ≤ 50 000 000 | ≤ 43 000 000 |

Létszám ÉS (árbevétel VAGY mérleg). A kategóriák mikro → kis → közép sorrendben vizsgálandók. A pénzügyi küszöb közvetlen összehasonlítás, nincs +1 vagy tolerancia. HUF-bemenetnél az EUR-korlátot a rögzített HUF/EUR értékkel szorozzuk. EUR-bemenet esetén a pénzügyi adatot ugyanazzal az árfolyammal normalizáljuk HUF-ra. A felület és dokumentum kerekítése nem változtatja meg a számítást.

## Kapcsolatok

- A saját vállalkozás 100%-ban szerepel.
- Vállalkozási tulajdonos többségi szavazata vagy rögzített meghatározó irányítási joga kapcsolódást hoz létre.
- Kapcsolódási láncon keresztül minden releváns cég a saját kapcsolódó blokkba kerül, 100%-kal. Az indirekt részesedések szorzata nem írja felül a kapcsolódást.
- Ha nincs kapcsolódás és a tőke/szavazat közül a magasabb legalább 25%, a közvetlen vállalkozási kapcsolat partnerként kezelhető. A befektetői kivételt külön, indoklással kell rögzíteni.
- Az elsődleges kapcsolódó blokk releváns partnerei saját kapcsolódó blokkukkal együtt, partneraránnyal szerepelnek.
- Partner partnerét nem adjuk automatikusan hozzá.
- Ugyanazon cég csak egy adatblokkban szerepel. Több partnerkapcsolat ugyanahhoz a blokkhoz szakértőileg meghatározott végső arányt igényel.
- Az önálló döntés nem írja felül észrevétlenül a bizonyított kapcsolódási láncot; az ellentmondás blokkoló ellenőrzési pont.

A természetes személy tulajdona önmagában nem automatikus partnerél két vállalkozás között. A közös fellépéshez a releváns cégek között külön döntés, indoklás, forrás és piaci megállapítás kell. A rokonság nem önálló automatikus kapcsolódási szabály.

## Időbeli háló

Az ügyben kiválasztható a zárónapi vagy a vizsgálati napi háló. A kapcsolatok kezdete/vége alapján a program csak az adott időpontban érvényes kapcsolatokat használja. Egy adott időpontban az ismert tulajdoni vagy szavazati arányok összege nem haladhatja meg a 100%-ot.

A zárást követő, azonnali hatású irányításváltozásnál a vizsgálati napi háló és az új, releváns adatblokk alkalmazását külön rendezni kell. A minősítés célja szerint megfelelő időpontválasztás a szakértő felelőssége.

## Kétéves állapot

A program a három egymásba ágyazott mérethatár teljesülését külön követi. Ismert korábbi jogállapot esetén egy határ státusza két egymást követő azonos eltérés után változik. Például kis → éves közép → éves nagy esetén a kis határ két egymást követő évben sérül, a közép határ csak egyszer: a történeti méret közép lehet. Nem pusztán két éves kategória minimumát vagy maximumát vesszük.

Ha nincs ismert korábbi állapot, két azonos megfigyelés igazolja a határ teljesülését vagy nem teljesülését. Eltérő évek esetén további előzmény szükséges. A hiányzó év vagy nem egymást követő évek megszakítják a megfigyeléssorozatot.

Az előzményként megadott jogi minősítés a legelső vizsgált év előtti állapot legyen. Ha ez nem ismert, az ügyben további korábbi év felvehető. Az azonnali strukturális joghatást csak indokolt és megerősített szakértői eseménydöntés alkalmazza.

## Beszámoló és árfolyam

Elfogadott, a vizsgálat napján már rendelkezésre álló beszámoló szükséges. Forrás, időszak és mérési módszer rögzítendő. Hiányzó mutató nem nulla. Rövid üzleti év vagy becslés évesítése külön dokumentálandó. A támogatási EU-profil AWU létszámmódszert kér.

Az árfolyam érvényességi napja a releváns zárónap. Az új vállalkozás becsléséhez a megvalósított magyar profilszabály az előző év utolsó napját használja; alkalmazhatóságát a szakértő ellenőrzi. A jegyzés nem lehet az érvényesség után vagy tíz napnál korábban. A forrás és megerősítés kötelező.

A konszolidált adatban megjelölt, azonos beszámítási súlyú cégek egyedi adatait a motor kizárja az ismételt összegzésből. Átfedő vagy eltérő súlyú konszolidáció blokkolja a jóváhagyást, amíg a szakértő megfelelő adatokat nem rögzít.

## Közjogi tulajdon

A közjogi közvetlen arányokat a motor figyelembe veszi. A teljes közvetlen/közvetett arányhoz indokolt szakértői összesítés kell. Magyar profilnál a megvalósított határ > 25%, EU-profilnál ≥ 25%; az alkalmazandó szöveget és kivételeket jóváhagyáskor külön ellenőrizni kell. A közjogi kizárás külön eredmény, nem számszerű nagyvállalati kategória.

## Transzferár

A méretbesorolás alapján a személyi mentesség vizsgálhatóságáról készül szöveg. A program nem állít automatikus ügyletszintű nyilvántartási kötelezettséget pusztán a közép- vagy nagyvállalkozási méretből. Az adott adóév, a kapcsolt ügyletek és mentességek külön vizsgálatot igényelnek.

## Kötelező ellenőrzés

A motor hiány esetén számszerű előzetes eredményt is mutathat, de a véglegesítés blokkolt. Csak egy rendezett alapforgatókönyv hagyható jóvá. A „minden cég 100%” érzékenységi forgatókönyv nem ad külön végleges jogi minősítést.

A hivatalos jogforrások és az MNB élő elérése a fejlesztési környezetben hálózati korlátozás miatt nem volt teljeskörűen igazolható. Az alkalmazás ezeket a megállapításokat nem tekinti automatikusan ellenőrzött jogi ténynek.
