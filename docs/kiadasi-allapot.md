# KKV és Tao – kiadási állapot, 2026.10.09.

A jelenlegi csomag kibővített, tesztelhető verzió. A transzferár harmadik modul, nincs a jelenlegi fejlesztési és elfogadási körben.

## Az első éles kiadás 100%-ának feltételei

- Közös, világos felület; külön KKV- és Tao-vizsgálat és jóváhagyás.
- OPTEN PDF-ek behúzása, forráshű kiolvasás, kézi javítás és kifejezett adatátvétel.
- Új és meglévő ügyek kezelése, ellenőrizhető számítások és szakértői döntések, források és korábbi verziók megőrzése.
- A vállalt automatikus jogalapokhoz elfogadott referenciaeredmények. A nem automatizált esetek felismerhető, dokumentálható szakértői útja.
- A ténylegesen vállalt vizsgálati napokra és időszakokra ellenőrzött jogszabályforrások.
- Word/PDF/Excel eredmények, jogosultságok, helyi mentés-visszaállítás, kipróbált Windows-telepítés és frissítés.

## Ebben a fejlesztési körben elkészült

- BVK szerepek, elkülönült kezelt vagyon és vagyonkezelői szavazati jogállás külön adatként.
- Tao-telephelyi tények, d)–e) jelzések, a fővállalkozás a)–c) jogalapjához kötött kiterjesztés. Az ügyvezetési f) jogalap nem terjed tovább ezen az úton.
- Meglévő KKV/Tao-ügy frissítése új PDF-csomagból, szereplő-egyeztetés és előző/új értékek összehasonlítása. Kiválasztás nélküli automatikus felülírás nincs.
- Elavult összehasonlítás elutasítása, új tervezet, változatlan korábbi jóváhagyott pillanatkép. A szakértői szavazati felülbírálat megmarad.
- A hiányos új beszámolósor nem emeli át egy korábbi konszolidált sor hiányzó összegeit egyedi adatnak. A megőrzött egyedi adat forrása az új forrás mellett megmarad.
- Jogi időállapot és forrás a KKV-ban is; későbbi jogi forrás történeti alkalmazhatóságának dokumentálása mindkét modulban.
- Ellenőrzött adatmentés, a korábbi adatokat megőrző visszaállítás és programcsomag-frissítés, Windows-indítókkal.

A korábbi verzióban importált BVK-részesedéseket külön újra kell ellenőrizni. A régi ügyeket nem írjuk át csendben az új BVK-jogállásra; az új PDF-összehasonlításban és a szavazati szerkesztőben lehet rendezni őket.

## Elvégzett ellenőrzés

- **120 automatikus teszt sikeres.** Többek között közvetett és rokonsági szavazat, irányítás, telephely, BVK, dátumhatárok, szakértői elsőbbség, meglévő ügy frissítése, jóváhagyott verzió megőrzése, jogosultság, sérült mentés elutasítása és visszaállítás.
- Teljes KKV-böngészőfolyamat: létrehozás, adatbevitel, jóváhagyás, Word/PDF, ügyfélhozzáférés és adatbekérés.
- Mind a **12 feltöltött OPTEN-PDF** tényleges böngészős behúzása; mindkét modul létrehozása és meglévő ügy frissítése, szerkesztők és exportok.
- **360, 390, 768, 1366, 1440 px** nézetek az import, összehasonlítás és Tao-folyamatokban; billentyűzetes kezelés; böngészős JavaScript-hiba nélkül.
- Függőség-összeférhetetlenséget a `pip check` nem talált.

A PDF-feldolgozási siker nem jelenti a konkrét ügy teljes jogi minősítésének igazolását. A tesztadatok és az ügyféliratokat tartalmazó képernyőképek nem kerülnek GitHubra.

## Még nyitott élesítési feltételek

1. **Natív Windows/OneDrive próba:** a felhasználó tényleges gépén PDF-import, programfrissítés, mentés és visszaállítás. Itt Linuxon a hordozható logikát tudtuk ellenőrizni.
2. **2024/2025 történeti jogszabály-összevetés:** a feltöltött források részben 2026-osak, és a Jogtár/NJT hálózati elérése blokkolt. A források hiánya nem írható felül szoftverteszttel.
3. **Szakértőileg elfogadott valós referenciaügy:** a Pölöskei-anyagok végső KKV-eredményének és Tao-mátrixának összevetése a dokumentált, igazolt rokonsági, BVK- és irányítási tényekkel. A hiányzó háttérnyilatkozatokra nem gyártunk választ.
4. **Az automatizálás vállalt határa:** körkörös háló, összetett családi/irányítási vegyes aggregálás, BVK-joggyakorlás teljes automatikus hozzárendelése és speciális célú Tao-fogalmak továbbra is indokolt szakértői értékelést igényelnek. A rendszer ezt kézi döntéssel támogatja; teljes automatikus lefedettséget nem állítunk.

Ezek lezárásáig nem nevezzük a csomagot 100%-ban éles kiadásnak. A fejlesztés előtti visszatérési pont és a helyi frissítés lépései: [Windows-karbantartás](windows-karbantartas.md).
