# KKV műhely

Magyar nyelvű, működő szakértői webalkalmazás KKV-vizsgálatokhoz: cégháló, éves adatok, pontos számítás, verziók, jóváhagyás és Word/PDF állásfoglalás. A csatolt munkafüzet két éves példáját reprodukálja, és javítja a feltárt 25%-os, összegzési és pénzügyi határértékhibákat.

## Új tesztmodul

Az OPTEN PDF-ek drag-and-drop importja szerkeszthető ellenőrző nézetet nyit; ugyanabból a feltöltésből külön KKV- és Tao-tervezet készül. [Kipróbálás és a tesztverzió határai](docs/pdf-tao-tesztverzio.md), [jogi források állapota](docs/jogi-forrasok.md).

## Beszélgetős segítség

KKV- és Tao-ügyekben célzott hiánymagyarázat, szabad szöveges AI-kérdezés, jóváhagyható kitöltési javaslat és diktálás. [API-beállítás és működés](docs/beszelgetos-segitseg.md).

## Indítás

Python 3.11+ szükséges. PDF-exporthoz a `soffice` paranccsal elérhető LibreOffice is kell. A jelenlegi felhőkörnyezetben ezek rendelkezésre állnak.

```bash
cd /workspace/KKV-vizsgalat
bash scripts/install.sh
bash scripts/start.sh
```

Alapértelmezett cím: `http://127.0.0.1:8000`. Az első megnyitáskor **saját adminisztrátori fiókot** kell létrehozni legalább 12 karakteres jelszóval. Nincs előre beállított jelszó. A „Mintavizsgálat” gomb fiktív nevekkel betölti az Excel számszerű példáját; a minta ellenőrizetlen kapcsolatokat és árfolyamokat tartalmaz, ezért tervezet.

A felhőfeladat meglévő checkoutját kell használni. Új Git worktree létrehozása a futtatáshoz nem szükséges.

Windows alatt a letöltött csomag gyökerében kattints duplán az **`INDITAS_WINDOWS.bat`** (az `Inditas-Windows.cmd` is ezt indítja) fájlra. Python 3.12 szükséges; az indító létrehozza a virtuális környezetet és ellenőrzi a függőségeket. Az első indításkor add meg a kicsomagolt Poppler mappájának teljes útvonalát. A `pdftotext.exe` helyét az alkalmazás a saját `data/tool-paths.json` fájljába menti, így új PowerShell-ablak esetén is működik a PDF-import. A böngésző automatikusan megnyílik; az indító ablak maradjon nyitva. Leállítás: Ctrl+C.

Frissítés előtt állítsd le a korábbi kiszolgálót. Másold az új csomag tartalmát a korábbi alkalmazásmappába, a programfájlok felülírásával. **A saját `data` és `.venv` mappát őrizd meg**: előbbi tartalmazza a fiókokat, ügyeket és a PDF-kiolvasó beállítását. Az indító ugyanabban a mappában legyen, ahol az `app` és a `requirements.txt`. Frissítés után a böngészőben Ctrl+F5.

## Napi munkafolyamat

1. Új vizsgálat létrehozása vagy a meglévő Excel importja.
2. Ügyfél, vizsgálati nap, jogi profil és vizsgált évek rögzítése.
3. Vállalkozások, személyek, tulajdoni/szavazati kapcsolatok, irányítási jogok és rokonság felvétele.
4. Beszámolók, források, elfogadási dátumok és az MNB-árfolyam megadása.
5. A szükséges kapcsolati, közös fellépési és piaci döntések indokolt rögzítése és ellenőrzése.
6. Mentés: új verzió és friss számítás készül. Az „Ellenőrzés” nézet mutatja a véglegesítést akadályozó hiányokat.
7. Szakértői jóváhagyás után a Word/PDF állásfoglalás átadható. Jóváhagyás előtt az export „TERVEZET”.

Az ellenőrzések minden nyitott kérdésnél megmutatják a hiányzó tényt, annak jelentőségét és a szükséges teendőt. A **Rendezés** gomb az érintett cég, kapcsolat vagy beszámoló megfelelő évi adatához visz; alapból az adott év teendői jelennek meg. A másik év külön választható, és a „Minden vizsgált év” nézet együtt mutatja őket. A döntés ellenőrzése az adott évre vonatkozik; az összes évre külön jelölőnégyzet adható meg. A szerkesztőablakok **Mentés és újraszámítás** gombja az ügyet is menti, frissíti az ellenőrzéseket, és megmutatja a beszámítás változását. A táblázatban közvetlenül beírt éves adatokhoz továbbra is a fő **Mentés** gomb használható. Hiányzó indok vagy ellenőrzés esetén a kérdés megmarad, konkrét útmutatással.

A rokonsági viszony mellett láthatók az érintett cégpárok és kapcsolati döntéseik. A rokonság rögzítése önmagában nem változtatja meg az összeszámítást; a közös fellépés és a releváns piaci kapcsolat külön igazolt döntést igényel.

A **Cégháló** nézetben a szereplők húzással vagy nyílbillentyűkkel mozgathatók, a nyilak együtt mozognak velük. Az **Elrendezés mentése** az ügy új verziójában tárolja a pozíciókat; az elrendezés az évek közötti váltáskor is megmarad. Az **Automatikus elrendezés** visszaállítja az alaphelyzetet, amelyet külön el kell menteni. A háló SVG és PNG formátumban letölthető az aktuális pozíciókkal, minősítésekkel és hálóidőponttal. A képen jelöljük a nem mentett adatokat és az előzetes minősítést.

Az elemző adatot szerkeszt. Jóváhagyó szakértő és adminisztrátor véglegesíthet. A jóváhagyó külön megerősíti a pénzügyi forrásokat, a kapcsolati tényállást és az alkalmazandó jogszabályi időállapotot. A rendszerbeli jóváhagyás nem elektronikus aláírás.


A **Tao-kapcsoltság** külön szolgáltatás a felső menüben (`/tao`). Az **Ellenőrzés** lapon ugyanaz a számláló szerepel a fülön, a kártyák felett és a mentési visszajelzésben. A minősítés, a forrásirat feldolgozása vagy a vizsgálati keret rendezése után a megfelelő kártya eltűnik. A „nem dönthető el” minősítés nyitott kérdés marad, részleges állásfoglalásban is.

Tao-szerkesztés közben az újraszámítás szükségessége látszik; mentéskor új verzió, friss szavazati/irányítási számítás és változásmagyarázat készül. A forrástények változásakor a változatlan korábbi döntések megerősítése megszűnik, ismét ellenőrizni kell őket. A rokonsági mező melletti szöveg elmagyarázza az összeszámítás feltételeit. A Tao-cégháló húzható, billentyűzettel mozgatható, menthető és SVG/PNG formátumban letölthető; a mentett elrendezés a Word/PDF-állásfoglalásban is megjelenik. Az ábra és a számított jelzések nem helyettesítik a cégpáronként indokolt jogi döntést.

## Generált állásfoglalás

Az ügy adataiból felépített Word/PDF tartalmazza a megbízás tárgyát, az EUR- és HUF-határokat és árfolyamokat, a kapcsolati minősítéseket, az éves összeszámítás indokolását, a kétéves szabály levezetését és a következtetést. Több cég esetén külön 100%-os érzékenységvizsgálat is készül; ez nem önálló jogi minősítés. Mellékletként szerepelnek a részletes táblázatok, kapcsolati indokok, forrásadatok és az évenkénti cégháló a mentett pozíciókkal. A szöveges előnézet ugyanazt a generátort használja, mint az export. A besorolás kerekítés előtt, a hiányzó adatok jelölésével történik.

A dokumentum A4-es, oldalszámozott; a széles mellékletek fekvő tájolásúak. Az export a kiválasztott mentett ügyverzió adataiból készül. Jóváhagyott verzióban szerepel a szakértő neve, a jóváhagyás ideje és a verziószám; a tervezet külön jelölt. A mintadokumentum kizárólag szerkezeti referencia, annak cégnevei és állításai nem kerülnek át az ügyekbe.

Az ellenőrzési nézetben közvetlenül olvashatók a feldolgozatlan ügyfélválaszok. A jóváhagyás előtt a rendszer megmutatja a hiányzó feltételeket, és mindhárom szakértői visszaigazolást kéri. Mentési hiba esetén a szerkesztőablak megmarad a beírt adatokkal; újrapróbáláskor nem keletkezik második szereplő. A hibás számezők mellett szöveges javítási útmutató jelenik meg.

## Ügyfélhozzáférés

Az adminisztrátor a „Munkatársak” nézetben `Ügyfél` szerepkörű fiókot hozhat létre, majd az „Ügyadatok” ablakban hozzárendelheti az ügyhöz. Az ügyfél:

- kizárólag a saját ügyeit látja;
- dokumentumot és adatbekérési választ küldhet be;
- a jóváhagyott eredmény összesített mutatóit és állásfoglalását kapja meg;
- nem kapja meg a belső munkafüzetet, szerkesztési adatokat, számítási konfigurációt vagy más ügyfelek dokumentumait.

Új változat szerkesztésekor a korábban jóváhagyott pillanatkép megmarad. Az ügyfél addig azt a jóváhagyott dokumentumot látja. A beérkezett új válaszokat a munkatársnak feldolgozottként kell jelölnie az új jóváhagyás előtt.

## Adatok és import

- A számítási motor **HUF-ban és Decimal számokkal** dolgozik. A felület pénzügyi beviteli mezői **ezer HUF / ezer EUR** egységűek.
- A tulajdon és szavazat **0–100 százalék**, nem 0–1 arány.
- A létszám tört érték is lehet. EU-profilnál AWU módszer szükséges.
- Az eredeti „Tulajdonosi struktúra” és „Pénzügyi adatok_…” munkalapok támogatottak. Az import a mentett számértékeket olvassa; Excel-képleteket és makrókat nem futtat.
- Az eredeti kézi befolyásadatból ellenőrizendő kapcsolati döntés készül; az import nem teszi automatikusan jogilag igazolttá.
- Saját adatbekérő XLSX-sablon is letölthető. Ennek első vállalkozási sora a vizsgált cég. A sablon adatbevitelre szolgál, nem tartalmaz minősítő képleteket.
- A hiányzó érték nem nulla. Hiányos beszámoló vagy nem ellenőrzött árfolyam mellett nem lehet jóváhagyni.

## Számítási szabályok és körülhatárolás

Lásd [RULES.md](RULES.md). A program kezeli a vállalkozások közötti többségi szavazatot, megadott irányítási jogokat, kapcsolódási láncot, releváns partnerblokkokat, dokumentált közös fellépési döntéseket, kompatibilis konszolidált adatok kizárását és a kétéves állapotot.

A több partnerútvonalból adódó bizonytalan arányt nem találja ki: a szakértőnek indokolt összeszámítási felülbírálatot kell rögzítenie. Különböző súlyú, átfedő konszolidáció vagy nem összehasonlítható időszak esetén rendezett forrásadat szükséges. USD/egyéb devizájú beszámolót dokumentáltan HUF-ra vagy EUR-ra átszámított adatként lehet bevinni.

A minősítés jogi profilja és a cégháló időpontja az ügyadatokban választható. Alapértelmezés szerint az egyes évek zárónapi hálója számít. A vizsgálati napi háló alkalmazását és a szerkezeti változások joghatását a szakértő dönti el. Az alkalmazás nem végez automatikus jogszabálykövetést vagy külső cégadat-szolgáltatói lekérést.

## MNB

Az „MNB-lekérés” a rögzített napra érvényes, legutolsó legfeljebb 10 napon belüli hivatalos EUR-jegyzést kéri le a fix MNB SOAP-végpontról. TLS-ellenőrzés aktív. A jelenlegi felhőkörnyezetben az MNB-domain hálózati tiltásba ütközhet. Ilyenkor az árfolyam és hivatalos forrás kézzel rögzíthető és ellenőrizhető.

Automatikus eléréshez a környezetben `www.mnb.hu` hozzáférése szükséges. A hálózati engedélyezés és a hivatalos szolgáltatás élő ellenőrzése külön konfigurációs lépés; a tesztek SOAP-válaszfeldolgozásának ellenőrzése önmagában nem igazol élő elérést.

## Tárolás és üzemeltetés

Az első verzió egyetlen szerverpéldányban fut, SQLite adattárolással. A `data/` könyvtár tartalma:

- `kkv.sqlite3`: fiókok, hash-elt jelszavak, munkamenetek, ügyek, verziók és napló;
- `uploads/`: feltöltött forrásdokumentumok;
- `exports/`: generált, verzióhoz kötött dokumentumok.

A könyvtár Gitből kizárt. Mentéskor az adatbázist és a dokumentumokat együtt kell megőrizni. Futó adatbázishoz a SQLite backup API használható; egyszerű fájlmásolást leállított alkalmazásnál végezzen. A csomag nem tartalmaz ügyféladatot vagy előre létrehozott fiókot.

| Változó | Alapérték / cél |
|---|---|
| `KKV_DATA_DIR` | A projekt `data/` mappája; külső tartós tárolóra átirányítható |
| `KKV_HOST` | `127.0.0.1`; nyilvános üzemeltetésnél megfelelő infrastruktúrához igazítható |
| `KKV_PORT` | `8000` |
| `KKV_SECURE_COOKIES` | HTTPS üzemeltetéskor `1` |
| `KKV_CHROMIUM` | Opcionális Chromium-executable a böngészőteszthez |

Nyilvános üzemeltetéshez HTTPS, tartós adatmentés és saját üzemeltetési beállítások szükségesek. Az első adminisztrátort helyben hozza létre a hálózati közzététel előtt. Nyilvános telepítés nem történt.

## Ellenőrzés

```bash
.venv/bin/python -m unittest discover -s tests -t . -v
```

A böngészőteszthez Playwright és Chromium kell:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/smoke_browser.py
```

A teszt külön ideiglenes adattárral, véletlen tesztjelszóval és saját, 8011-es porton futó szerverrel dolgozik. Nem módosítja az alkalmazás ügyféladatait. Végigjárja a fióklétrehozást, mintaszámítást, mobil nézetet, bevitelt, jóváhagyást, Word/PDF-exportot, sablonletöltést és ügyfél-adatbekérést. A kimenetek a Gitből kizárt `test-results/` mappában vannak.

## Projektfelépítés

```text
app/
  models.py       Validált bemenet, stabil azonosítók
  engine.py       Számítás és minősítési állapot
  db.py           SQLite, verziók és audit
  main.py         API, belépés, szerepkörök, dokumentumok
  importers.py    Excel-import és adatbekérő sablon
  reports.py      Állásfoglalás-generálás
  static/         Magyar felület, CSS és natív JavaScript
scripts/          Telepítés, indítás, böngészőteszt
tests/            Számítási és API-tesztek
```

A felület buildlépés nélkül fut. Több szerverpéldányos, nagyobb szervezeti telepítéshez PostgreSQL és közös dokumentumtároló bevezetése külön üzemeltetési bővítés.

Helyi biztonsági mentés, visszaállítás és ZIP-ből frissítés: [Windows-karbantartás](docs/windows-karbantartas.md).


## Döntésmentés és állásfoglalások – 2026. október 10.

A Tao-döntésnél a **Mentés és ellenőrzöttnek jelölés** lezárja a forrással és indokkal igazolt kapcsolt / nem kapcsolt minősítést. A **Mentés tervezetként** nyitva hagyja. A **Mentés nyitott kérdésként** a „nem dönthető el” eredményt és a következő lépést rögzíti; ez a tétel továbbra is ellenőrizendő. A negatív minősítésnél a releváns jogalapok ellenőrzését külön meg kell erősíteni. A legördülők választásai mellett részletes magyarázat jelenik meg.

Az **Ügyadatok** alatt külön piaci értékelés, feltételezések, a kiadó szervezet és az aláíró is rögzíthető. Az **Ellenőrzés** nézetből bírósági döntés / jogforrás adható hozzá hivatalos linkkel, releváns idézettel és ügyre szabott indokkal. Az ellenőrizetlen hivatkozás kutatási tétel marad; a program nem alkalmazza automatikusan.

A Word a megküldött minta Garamond tipográfiáját, egyszerű címsorait és visszafogott táblázatait követi. A Tao-vélemény is részletes tényállást, befolyásszámítást, jogalapot, forrást és következtetést tartalmaz, külön feltételezés-, piacvizsgálati és jogforrásrésszel. [Megnyitható fiktív Word/PDF-minták](docs/peldak/README.md).

A **PDF feltételek** gomb külön mutatja a LibreOffice-alapú PDF-exportot és a Poppler-alapú PDF-beolvasást. Exporthoz telepítsd a [LibreOffice-t](https://www.libreoffice.org/download/download-libreoffice/), majd indítsd újra az alkalmazást. A szokásos Windows telepítési helyet automatikusan felismeri; a konverzió rövid helyi ideiglenes útvonalakon fut, saját LibreOffice-profillal. DLL-hibánál a PDF-beolvasó a Poppler teljes csomagjának helyreállítását kéri.
