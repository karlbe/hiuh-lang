# HIUH Självkompilering - TODO

## Mål
Pipeline `hiuh-tokenizer.exe < source.hiuh | hiuh-parser.exe > out.s` ska kunna
kompilera sig själv. Python-kompilatorn är ett mellansteg — slutmålet är att
hela verktygskedjan kompileras av sig själv utan Python.

---

## Status

### Tokenizer (src/hiuh-tokenizer.hiuh) — KLAR (kompileras av Python-kompilatorn)
Hanterar `Inkludera` via `LäsFil` (splitsas in i tokenströmmen transparent).
Saknar: `LäsFil` i keyword-listan (nödvändigt för self-hosting via pipeline).

### Kompilator (compiler/hiuh-native.py) — KLAR
Referensimplementation. Stödjer allt HIUH har.

### Pipeline-parser (src/hiuh-parser.hiuh) — PÅGÅR (26/26 tester gröna)
Hanterar: SET, SKRIV_NL, OKA, MINSKA, IF/END, SALANGES/END, BREAK,
MINDRE AN, STORRE AN, READ, EXIT, LAGRA, TECKEN, JAMFOR, JAMFOR_BUF,
KOPIERA_BUF, FUNKTION/GE/ANROPA (med typannotering AR TEXT).

---

## Vad saknas för självkompilering

### C. Pipeline-parser saknar features som Python-kompilatorn har  [SPRÅKGAP]
Dessa konstrukt fungerar i Python-kompilatorn men genereras inte av pipeline-parsern.
Ett HIUH-program som använder dem kan kompileras med `-Py` men inte med pipeline.

| Konstrukt | Token | Anteckning |
|-----------|-------|------------|
| `Skriv x` (utan nyrad) | `SKRIV` | Python har printf utan `\n`; parsern saknar handler |
| `För i från 0 till N` | `FOR` | Se B4 — räknarloop saknas i parsern |
| `Sålänge` / `Om` med `inte är` | `INTE AR` | Se B1 |
| `Sålänge` / `Om` med `texten` | `TEXTEN` | Se B3 |
| `Sålänge` / `Om` med `tom` | `TOM` | Se B2 |
| `LäsFil text i buf` | `LAS_FIL` | Se B5 |

Konsekvens: program som använder ovanstående kompileras korrekt av Python-kompilatorn
men producerar inkomplett eller felaktig assembly via pipeline. Gapen C och B är samma
lista — åtgärda B1–B5 + FOR så försvinner C automatiskt.

---

### A. I tokenizern (src/hiuh-tokenizer.hiuh)

#### A1. `LäsFil` saknas i keyword-listan  [BLOCKERAR TOKENIZER-SELF-HOSTING]
När pipeline-parsern kompilerar tokenizern, tokeniseras tokenizerkällan av sig
själv. `LäsFil` är inte ett känt nyckelord → emitteras som identifierare, inte
som `LAS_FIL`-token.
Lösning: lägg till `Sätt träff till Jämför ord_buf med LäsFil` → `SkrivNyRad LAS_FIL`
i emit_word, precis som övriga nyckelord.

---

### B. I pipeline-parsern (src/hiuh-parser.hiuh)

#### B1. INTE AR — negation i IF och SALANGES  [BLOCKERAR BÅDA]
`Om idx2 inte är 99`   → `IF idx2 INTE AR 99`
`Sålänge hm inte är 0` → `SALANGES hm INTE AR 0`

Parser-källan: ~10 förekomster. Tokenizer-källan: 2 förekomster.
Lösning: när handleren läser nästa token efter variabelnamnet och det är INTE,
sätt negerings-flagga och läs AR; byt sedan hopp (jne↔je).

#### B2. TOM-jämförelse i SALANGES  [BLOCKERAR BÅDA]
`Sålänge rad inte är tom` → `SALANGES rad INTE AR TOM`
`Sålänge tok inte är tom` → `SALANGES tok INTE AR TOM`

Variant av B1: TOM-token = tom sträng. Kolla om buffertens första byte är 0.
(`cmpb $0, rad_buf(%rip) / je exit_label` vid INTE AR TOM)

#### B3. TEXTEN-jämförelse i IF och SALANGES  [BLOCKERAR PARSER-SELF-HOSTING]
`Om tok är texten SET`          → `IF tok AR TEXTEN SET`
`Sålänge tok inte är texten GE` → `SALANGES tok INTE AR TEXTEN GE`

Parser-källan: ~15 förekomster i hantera(). Tokenizern: inga.
Lösning: när värdetokenet är TEXTEN, läs nästa token som literalsträng,
emittera strcmp(tok_buf, "SET") + test %eax + je/jne beroende på negering.
Kräver att Text-variabler har en associerad buffert (t.ex. tok_buf för `tok`).

#### B4. FOR-loop  [BLOCKERAR TOKENIZER-SELF-HOSTING]
`För i från 0 till 255` → `FOR i FRAN 0 TILL 255`

Tokenizern: 1 förekomst (teckenscanningen per rad). Parsern: ingen.
Lösning: emittera räknarloop: `mov $from, %rXX; L_top: cmp $till, %rXX;
jge L_end; [body]; inc %rXX; jmp L_top; L_end:`.

#### B5. LAS_FIL — `LäsFil text i buf`  [BLOCKERAR TOKENIZER-SELF-HOSTING]
När tokenizern (kompilerad via pipeline) kör, anropas `LäsFil text i ord_buf`
för att ladda inkluderade filer. Pipeline-parsern saknar handler för LAS_FIL-tokenet.

Dessutom: READ-varianter i pipeline-genererad assembly kontrollerar INTE
`_hiuh_incl_buf` än — det gör bara Python-kompilatorns genererade kod.

Lösning:
1. Lägg till LAS_FIL-handler i parsern → emittera fopen/fread/fclose-assembly
   (samma logik som Python-kompilatorns LAS_FIL-handler)
2. READ/SALANGES-hanterarna i parsern behöver emittera `_hiuh_incl_buf`-check
   före fgets (eller anropa en delad subrutin)

---

## Ordning

1. B1 — INTE AR (IF + SALANGES) — lågt hängande frukt, avblockerar mest
2. B2 — TOM-jämförelse — variant av B1, enkelt efteråt
3. A1 — LäsFil i tokenizer keyword-lista — en rad
4. B3 — TEXTEN-jämförelse — avblockerar parser-self-hosting
5. B4 — FOR-loop — avblockerar tokenizer-self-hosting
6. B5 — LAS_FIL handler + READ incl-buf check i pipeline-parsern

---

## Verifieringsplan

1. Kompilera parser via pipeline → alla 26 pipeline-tester gröna
2. `hiuh-tokenizer.exe < src/hiuh-parser.hiuh | hiuh-parser.exe > parser2.s`
   Assemblera + länka → kör pipeline-tester med parser2.exe, alla gröna
3. `hiuh-tokenizer.exe < src/hiuh-tokenizer.hiuh | hiuh-parser.exe > tokenizer2.s`
   Assemblera → `tokenizer2.exe < src/test-arith-parser.hiuh | hiuh-parser.exe`
   ska ge samma output som original-tokenizern
4. Sluttest (fixpunkt): parser2.s == parser3.s
