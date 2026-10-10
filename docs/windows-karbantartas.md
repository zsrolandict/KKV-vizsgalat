# Helyi mentés, visszaállítás és frissítés

Az alkalmazás könyvtárában három új, dupla kattintással indítható Windows-eszköz található. A Python 3.12 és a már létrehozott `.venv` szükséges. Első telepítéskor az `Inditas-Windows.cmd` készíti elő a környezetet.

## Mentés

1. Dupla kattintás: **Mentes-Windows.cmd**.
2. Az ellenőrzött ZIP a program **backups** mappájába kerül, dátummal és időponttal.
3. Másolja ezt a ZIP-et a szokásos biztonsági mentési helyére is.

A mentés tartalmazza az adatbázist, a két modul verzióit és naplóját, a felhasználókat, az eredeti iratokat, az importcsomagokat és a helyi eszközútvonalakat. A SQLite-pillanatkép és a forrásmásolás idejére az alkalmazás írásai várakoznak. A mentés elkészülte előtt adatbázis-, hivatkozás- és SHA-256 ellenőrzés fut. Hiányzó forrásirattal nem keletkezik sikeres mentés. A ZIP bizalmas ügyféladatokat tartalmaz; nincs titkosítva.

## Visszaállítás

1. Állítsa le az alkalmazást az indítóablakban **Ctrl+C**-vel. Minden futó példányt állítson le; az automatikus ellenőrzés a szokásos 8000-es portot figyeli.
2. Dupla kattintás: **Visszaallitas-Windows.cmd**.
3. Illessze be a mentési ZIP teljes útvonalát; az idézőjel megengedett.
4. A program először külön ideiglenes könyvtárban ellenőrzi és állítja helyre a mentést. Csak siker után vált át rá.
5. A korábbi adatkönyvtár **data-before-restore-…** néven megmarad. A korábbi böngészős munkamenetek érvénytelenek; újra be kell jelentkezni.
6. Indítsa az **Inditas-Windows.cmd** fájlt.

A mentett Poppler-útvonal másik számítógépen eltérhet. Ilyenkor az indító ismét bekéri a telepítés helyét.

## Frissítés

1. Előbb mentse el a folyamatban lévő szerkesztést, majd állítsa le az alkalmazást.
2. Töltse le a jóváhagyott fejlesztési ág ZIP-jét a GitHubról. A ZIP legyen az alkalmazás mappáján kívül, például a Letöltések között.
3. Dupla kattintás: **Frissites-Windows.cmd**. Adja meg a ZIP teljes útvonalát. Kicsomagolt programkönyvtár is megadható.
4. Az eszköz ellenőrzi a csomag szerkezetét, adatmentést készít, majd cseréli a programfájlokat. A **data**, **.venv**, saját további fájlok megmaradnak. Az előző program a **backups/program-…** könyvtárba kerül. Fájlcserehiba esetén a már lecserélt fájlokat visszateszi.
5. A függőségek telepítése után az **Inditas-Windows.cmd** indítja az új verziót. Függőségtelepítési hibánál az indító újra megpróbálja a telepítést; ez nem törli az ügyadatokat.

Ha a jelenlegi telepítésben még nincsenek ezek az eszközök, első alkalommal a letöltött új csomag `app` könyvtárát, `requirements.txt` fájlját és Windows-indítóit másolja a program mappájába. A meglévő `data` és `.venv` könyvtárat őrizze meg.

## Visszatérés egy korábbi programhoz

Leállítás után a `backups/program-…` alatt megőrzött programfájlok visszamásolhatók. Ha az adatállományt is vissza kell állítani, a frissítés előtt készült ZIP-et használja. A program és az adatok visszaállítása külön lépés. A jelenlegi fejlesztés előtti Git-visszatérési pont: `b8ee93d2eb1aeaf6332bca428726b62332b4a474`.

## Ellenőrzési határ

A karbantartás Python-logikáját Linuxon, valódi SQLite-adatbázissal, sérült és veszélyes archívummal, megőrzött forrásokkal és program-visszatérési másolattal teszteljük. Natív Windows- és OneDrive-futtatás itt nem érhető el; ennek gyakorlati kipróbálása még kiadási feltétel.

Parancssori használat: `python -m app.maintenance backup`, `verify MENTES.zip`, `restore MENTES.zip --destination UJ_MAPPA`, illetve `update PROGRAM.zip`. A `--destination` csak új, még nem létező könyvtárat fogad el. A `KKV_DATA_DIR` beállítás egyedi adatkönyvtárra is használható.
