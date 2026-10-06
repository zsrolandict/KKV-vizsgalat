# Átadási ellenőrzés – KKV műhely v1

Ellenőrizve: 2026. október 6., a jelenlegi felhőkörnyezetben. Szabályverzió: `KKV-2026.1-szakertoi`.

## Eredmények

- **38 automatikus teszt sikeres**, nincs kihagyott teszt. A számítási motor, az API és az Excel-import ellenőrzése a `tests/` mappában található.
- A telepítő és az indító script ténylegesen lefutott; az ismételt telepítés is sikerült. A szerver újraindítása után az `/api/health` a várt szabályverzióval válaszolt.
- A Chromium böngészőben végigment az első adminisztrátori fiók létrehozása, a mintaszámítás, az összes cég 100%-os forgatókönyve, a mobil nézet, az új ügy adatbevitele, a szakértői jóváhagyás, a Word/PDF-export, a sablonletöltés, az ügyfél hozzárendelése és az ügyfél adatbekérési válasza.
- Az exportellenőrzés megnyitotta a létrejött Word- és PDF-fájlokat, és ellenőrizte a jóváhagyott eredmény tartalmát.
- A szerepköri/API-tesztek igazolták az ügyfél adatelkülönítését, a belső számítási adatok elrejtését, a jóváhagyott változat megőrzését új tervezet mellett, a verzióütközések kezelését és a hiányos ügy véglegesítésének tiltását.
- A böngészőteszt külön ideiglenes adattárral és véletlen tesztjelszóval futott. Az átadott alkalmazásban nincs előre létrehozott fiók.

## A csatolt Excel számszerű ellenőrzése

A ténylegesen csatolt munkafüzet importja 9 vállalkozást és 12 természetes személyt olvasott be. A munkafüzet szerinti alapforgatókönyv eredménye:

| Év | Létszám | Árbevétel HUF | Mérlegfőösszeg HUF |
|---|---:|---:|---:|
| 2024 | 126,5 | 3 273 330 500 | 1 888 382 000 |
| 2025 | 140,5 | 3 641 805 000 | 2 365 322 000 |

Az eredeti állományokat nem módosítottuk. A számszerű egyezés nem igazolja önmagában a tulajdonosi tényállást vagy a kézi kapcsolati döntéseket. Az import ezért ellenőrzendő tervezetet készít.

Külön teszt vizsgálja a pontosan 25%-os partnerséget, a 50%-os kapcsolatot, a szavazati/irányítási jogot, a kapcsolódási láncot, a partner partnerének kizárását, a kilencedik vállalkozás beszámítását, a pénzügyi küszöb feletti 1 Ft-ot, a kétéves állapotot, a konszolidációt, az időbeli kapcsolatokat és a Decimal pontosságot.

## Ami további külső ellenőrzést igényel

- Az MNB SOAP-válaszának feldolgozása és a hibakezelés automatizált tesztben sikeres. A hivatalos szolgáltatás élő elérését a jelenlegi hálózati korlátozás blokkolta. A `www.mnb.hu` engedélyt a mentett környezet-konfiguráció tervezete tartalmazza; alkalmazása után élő lekérés szükséges. Addig a kézi, forrással igazolt árfolyamrögzítés működik.
- Az alkalmazandó magyar/EU jogi időállapot és az adott ügy tényállása szakértői jóváhagyást igényel. A hálózati korlátozás miatt a hivatalos jogforrások teljes élő ellenőrzése nem történt meg.
- Nyilvános telepítés és új felhőfeladatból történő visszaállítás nem történt. A jelenlegi futtatás és a konfigurációtervezet mentése ellenőrzött; a környezet publikálása külön felhasználói lépés.

## Újrafuttatás

```bash
cd /workspace/KKV-vizsgalat
bash scripts/install.sh
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/smoke_browser.py
```

A böngészőteszthez Chromium és a PDF-ellenőrzéshez LibreOffice szükséges. A tesztkimenetek a Gitből kizárt `test-results/` mappába kerülnek. A forráscsomag nem tartalmaz adatbázist, ügyféliratokat, jelszavakat vagy tesztmunkameneteket.
