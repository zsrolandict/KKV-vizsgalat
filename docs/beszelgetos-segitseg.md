# Beszélgetős segítség a KKV- és Tao-vizsgálatokban

Az ügy tetején a **Beszélgetős segítség** gomb nyitja meg. A KKV-program először menti a megkezdett adatmódosításokat; hibás dátum vagy szám esetén előbb azt kell javítani.

## API beállítása

Adminisztrátorként nyisd ki az **AI-kapcsolat beállítása** részt. Add meg az OpenAI API-kulcsot és a használható modell nevét (alapértelmezés: `gpt-4.1-mini`), majd mentsd. A kulcsot a gép `data/ai-settings.json` fájlja tárolja; a program nem küldi vissza a böngészőnek. A `data` mappát és mentéseit a kulcs miatt is kezeld bizalmasan. Környezeti változóval az `OPENAI_API_KEY` és `OPENAI_MODEL` is használható, ezek elsőbbséget élveznek. A ChatGPT-előfizetés nem helyettesíti az API-szolgáltatást; annak használata külön díjazású lehet.

A program jelenleg az OpenAI Chat Completions API-hoz kapcsolódik. Nincs böngészőoldali közvetlen szolgáltatóhívás, nincs tetszőleges külső API-cím. API nélkül a helyi szabálymotor hiánymagyarázata elérhető, de ez nem értelmez szabad szöveget és nem készít automatikus kitöltést.

## Beszélgetés és kitöltés

Például: „Miért nem eldönthető még az Alfa és a Beta kapcsolata?” A szolgáltató megkapja az ügy **mentett adatait, számítását és a beszélgetés szövegét**. A feltöltött eredeti fájlokat nem küldi el a program; az ügybe már rögzített forrásidézetek a tényadatok részei. A küldés külön, feliratozott felhasználói művelet.

A válasz célzott tisztázó kérdést és kitöltési javaslatot adhat. A javaslat a séma és az azonosító-hivatkozások ellenőrzése után jelenik meg, a korábbi és új mezőértékekkel és várható számítási hatással. A **Jóváhagyom a kitöltést · mentés és újraszámítás** gomb az ügy szokásos, verziózott mentését használja. A javaslat elvethető; közben módosult ügyre nem alkalmazható.

Az AI nem erősíti meg szakértőileg a döntéseket, nem igazol forrásiratot, nem véglegesíti a vizsgálatot. Megváltozott tényadatok korábbi kapcsolati ellenőrzéseket nyithatnak újra. Az AI-nak nincs webes jogforráskutatása; nem tekinthető ellenőrzött ítéletforrásnak.

A beszélgetés a megnyitott böngészőlap memóriájában marad meg az adott ügyhöz; az oldal újratöltése törli. A jóváhagyott adatokat az ügy mentett verziója megőrzi.

## Diktálás

Támogatott böngészőben **Diktálás** gomb használható, mikrofonengedéllyel. A hangot a böngésző beszédfelismerő szolgáltatása dolgozza fel; a szöveg ellenőrizhető és szerkeszthető, és külön kell elküldeni. Ha nem támogatott, Windows alatt a **Win+H** rendszerfunkció is használható a kérdésmezőben.

## Ellenőrzés

A regressziós ellenőrzések külön tesztadatbázisban futnak. A kitöltési és szolgáltatói választesztek helyettesített AI-válaszokat használnak, így nem indítanak díjköteles API-kérést. Élő API-hozzáférést a saját kulcs beállítása után lehet ellenőrizni a felületen.
