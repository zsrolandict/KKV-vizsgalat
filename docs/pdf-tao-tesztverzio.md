# OPTEN PDF-import és Tao-munkafolyamat – első tesztverzió

Fejlesztési ág: `feat/tao-matrix`. A meglévő KKV-motor mellett külön Tao-adatmodell, eredmény, verzió és jóváhagyás működik. Az eredeti ügyfél-PDF-ek nem részei a repozitóriumnak.

## Kipróbálás

Python 3.11 vagy újabb, `pdftotext` (Debian/Ubuntu: `poppler-utils`) és a `requirements.txt` függőségei szükségesek. A PDF-jelentésekhez LibreOffice is kell; nélküle Word és Excel érhető el. A betűkészleteket az alkalmazás helyben szolgálja ki, OFL-licenccel.

```bash
bash scripts/install.sh
KKV_DATA_DIR=/tmp/kkv-proba bash scripts/start.sh
```

Saját gépen a szerver címén hozz létre tesztfiókot. A KKV-kezdőképernyő és a Tao-kezdőképernyő **OPTEN PDF-import** művelete ugyanazt a feltöltőt nyitja. Útvonalak: `/`, `/tao`, `/pdf-import?module=kkv`, `/pdf-import?module=tao`.

1. Húzd a cégadatlapokat és cégtörténeteket a feltöltőre, vagy válaszd ki őket. Egyszerre legfeljebb 20 fájl, összesen 20 MB.
2. Ellenőrizd és javítsd a cégneveket, azonosítókat, tulajdonosi/szavazati sorokat, időszakokat, vezetői jelölteket és pénzügyi adatokat. Minden forrásjelöltnél az eredeti PDF és az oldal/idézet elérhető.
3. Válassz vizsgálatot és vizsgálati napot; KKV esetén céget és éveket is. A külön adatellenőrzési megerősítés után új **tervezet** készül.
4. Ugyanebből a feltöltésből a másik szolgáltatáshoz is külön tervezet készíthető. A Tao-minősítés nem kerül át automatikusan KKV-kapcsolati döntésként.
5. A vizsgálatban folytasd a források, kapcsolatok, éves létszám, beszámoló-elfogadási dátum, árfolyamok és jogi időállapot ellenőrzését. Az adatimport jóváhagyása önmagában nem végleges állásfoglalás.

## Windowsos indítás és felület

Az `Inditas-Windows.cmd` fájl dupla kattintással indítja a helyi alkalmazást. Első alkalommal bekéri a Poppler kicsomagolt mappáját, ellenőrzi a `pdftotext.exe` futását és elmenti az útvonalat. Szóközös és magyar ékezetes útvonal is használható; nem szükséges tartósan átírni a Windows PATH változóját. A szokásos helyre telepített LibreOffice programot is felismeri. A beállítás saját `data/tool-paths.json` fájlban marad. Ha már fut a korábbi alkalmazás, előbb Ctrl+C-vel állítsd le.

A KKV belépőoldala és munkafelülete is fehér, halvány kékesszürke, sötétkék és türkiz stílust használ, helyben szolgált Manrope és DM Sans betűkkel. Laptopon felső navigáció, mobilon feliratos alsó navigáció működik. Az Eszközök menüben elérhető a sablon, a mintavizsgálat és a munkatársak kezelése.

A böngészős működést és a PDF-importot Linuxon ellenőriztük. A Windowsos indító natív Windows-futtatása ebben a felhőkörnyezetben nem ellenőrizhető; az útvonalkeresést és a mentett beállítás kezelését automatikus tesztek fedik le.

## Mit kezel a tesztverzió?

- Szöveges OPTEN cégadatlap és cégtörténet. A szkennelt, titkosított, sérült vagy más formátumú PDF célzott hibát ad; nincs OCR.
- Cégjegyzékszám alapú cégazonosság és a cégiratok névváltozatai. A természetes személy névazonossága jelölt; azonosságot és rokonságot szakértőnek kell igazolnia.
- Ismeretlen arány üresen marad. Az „50% feletti” szavazat nem kap kitalált számot. Az OPTEN gyűjtött „befolyás” nem válik automatikusan tulajdonrésszé.
- Tulajdon = szavazat jelölt feltételezés; külön dokumentált szavazat és indokolt szakértői felülbírálat is adható. A Tao-tényjelzésekben a szakértői adat élvez elsőbbséget.
- Közvetlen és közvetett szavazati befolyás számítása a Ptk. 8:2. § (4) szerint: a köztes vállalkozásban több mint 50% szavazat teljes beszámítást eredményez, pontosan 50% még arányos szorzást. Több útvonal és közvetlen szavazat összeadódik. A dokumentált >50% jelzésből nem képezünk pontos százalékot. A számítás a felületen és a Word/Excel-exportban tényazonosítókkal követhető. Körkörös, ütköző, ismeretlen vagy 100% fölé összegződő adatokból nem keletkezik automatikus minősítés.
- Érvényesség és cégbírósági bejegyzés/törlés külön mező. A Tao végdátum kizáró; a korábbi KKV-adatmodellbe ez egy nappal korábbi, befoglaló végdátummal kerül. Hiányzó kezdőnapból nem képzünk visszamenőleges KKV-tulajdoni sort.
- A PDF létszáma referenciaként jelenik meg. A kézi átemelés nem igazolja az éves módszertant; azt a KKV-vizsgálatban külön meg kell erősíteni. A pénzügyi értékek ezer forintról pontosan egyszer kerülnek forintra váltásra.
- Elkülönített, felhasználóhoz kötött importcsomag; forrásfájlok, hash, ellenőrzési pillanatkép és napló megőrzése. Külön jóváhagyás, verziók és Word/PDF/Excel Tao-export.

## Határok és következő lépések

A Tao-mátrix jogi minősítése indokolt szakértői döntésekből áll. A közvetlen/közvetett szavazati számítás már működik, és kapcsoltsági jelzést ad; önmagában nem végleges Tao-minősítés. A rokonság, meghatározó befolyási jogok, vezetői irányítás, BVK és speciális Tao-jogalapok teljes automatikus motorja még nincs implementálva. A körkörös hálók szakértői számítást igényelnek. A vezetői jelöltek az importellenőrzésben és a forrásokban szerepelnek; nem keletkeztetnek automatikus kapcsoltságot. A transzferár-kötelezettség teljes vizsgálata külön fejlesztési lépés. Lásd: [jogi források](jogi-forrasok.md).

Az import jelenleg új tervezetet hoz létre. Meglévő ügyhöz ismételt PDF-import és mezőnkénti összehasonlítás még fejlesztendő. Az új dokumentum hagyományos feltöltése a Tao-ügyben új, ellenőrizendő verziót készít; a korábban jóváhagyott pillanatkép megmarad.

## Ellenőrzés

```bash
KKV_DATA_DIR=/tmp/kkv-tests .venv/bin/python -m unittest discover -s tests -t . -q
.venv/bin/python scripts/smoke_browser.py
.venv/bin/python scripts/smoke_pdf_browser.py /sajat/utvonal/opten_cegadatlap.pdf /sajat/utvonal/opten_cegtortenet.pdf
```

A böngészőtesztek külön ideiglenes adatbázist használnak. A PDF-teszt tényleges drag-and-drop eseményt, módosítást, mindkét tervezetet, forráslétszám kezelését, Excel-letöltést és 360/390/768/1366/1440 px szélességet ellenőriz. Az első tesztverziót a felhasználó mind a 12 PDF-jével is ellenőriztük, külön ideiglenes tesztadatbázisban az automatizált regressziós tesztekkel együtt. A készülő képek és tesztkimenetek az ignorált `test-results/` alatt maradnak.
