# HIUH Självkompilering - TODO

## Mål
Pipeline `hiuh-tokenizer.exe < source.hiuh | hiuh-parser.exe > out.s` ska kunna
kompilera sig själv. Python-kompilatorn är ett mellansteg — slutmålet är att
hela verktygskedjan kompileras av sig själv utan Python.

---

## Status

### Tokenizer (src/hiuh-tokenizer.hiuh) — PIPELINE-KOMPILERAS MEN HÄNGER
- Python-kompilerad tokenizer fungerar korrekt
- Pipeline-kompilerad tokenizer2.exe assembleras och länkas OK
- Men tokenizer2.exe hänger vid körning (bekräftat med timeout-test)

### Kompilator (compiler/hiuh-native.py) — KLAR
Referensimplementation. Stödjer allt HIUH har.

### Pipeline-parser (src/hiuh-parser.hiuh) — PÅGÅR (31/31 tester gröna)
Hanterar: SET, SKRIV (utan nyrad), SKRIV_NL, OKA, MINSKA, IF/END, SALANGES/END,
BREAK, MINDRE AN, STORRE AN, READ, EXIT, LAGRA, TECKEN, JAMFOR, JAMFOR_BUF,
KOPIERA_BUF, FUNKTION/GE/ANROPA (med typannotering AR TEXT),
INTE AR (negation i IF+SALANGES), TOM (tom-strängkoll i IF+SALANGES),
TEXTEN (strcmp mot literal i IF+SALANGES, inkl. INTE AR TEXTEN),
FOR-loop (FOR i FRAN from TILL till).
Data-sektionen emitteras alltid i main-epilogen (oavsett om EXIT används).

---

## Fixade buggar

### C1: `Sätt x till y` (variabel-till-variabel-kopia) ✓ FIXED
**Problem:** `Sätt klar till i_ord` genererade tom kod i SET-handleren.
**Fix:** Lade till fallback-case i SET-handler: om token efter TILL inte är VARDET/JAMFOR/TECKEN/PLUS/MINUS, slå upp som variabel. Emittera `mov %rSRC, %rDST`.
**Resultat:** `klar` sätts nu vid ordgränser i FOR-loopen, emit_word anropas korrekt.

### C2: JAMFOR-literaler tokeniseras vid självkompilering ✓ FIXED
**Problem:** `Jämför ord_buf med Skriv` tokeniseras till `JAMFOR ord_buf MED SKRIV` → parsern genererar `strcmp(ord_buf, "SKRIV")` istället för `strcmp(ord_buf, "Skriv")`.
**Fix:** Lade till quoted string support:
- Tokenizer: använd `Jämför ord_buf med "Skriv"` (med citationstecken)
- Citattecken är inte keyword, så `"Skriv"` kommer genom som identifier-token
- Parser: ny `unquote_input_buf` funktion strippar citationstecken från literals
- Python compiler: samma quoting/unquoting support
**Resultat:** Nyckelord i JAMFOR-literaler överlever self-hosting intakt.

### C3: tokenizer2.exe hängning ✓ FIXED
**Problem:** tokenizer2.exe hängde när det kördes med enkel input.
**Causa:** Kombination av C1 och C2 — variabel-copy genererade tom kod + nyckelord-matchning misslyckades.
**Resultat:** Med C1+C2 fixade, tokenizer2.exe avslutas nu normalt (inom 5s timeout).
**Notering:** Output skiljer sig något från Python-kompilerad version (ordning av tokens/whitespace). Behöver ytterligare diagnos men HANG är löst.

---

## Nästa steg (i prioritetsordning)

1. **Debugga test failures (3/31 failing)** — 28/31 tests gröna, 3 assembly-fel i variabelkopia edge-cases
2. **Verifiera tokenizer2.exe output** — skiljer sig från Python-version, behöver granska check_skriv argument-handling
3. **B5: LAS_FIL i parsern** — krävs för att tokenizern ska kunna inkludera filer (blockerar full self-hosting)
4. **Sluttest** — parser2.s self-hosting när allt fungerar

---

## Klar-lista (för historik)

| Item | Vad |
|------|-----|
| B1 | INTE AR i IF + SALANGES |
| B2 | TOM-jämförelse i IF + SALANGES |
| B3 + B3a | TEXTEN-jämförelse + .bss för namngivna buffertar |
| A1 | LäsFil i tokenizer keyword-lista |
| SKRIV | Pipeline-parser hanterar SKRIV (utan nyrad): literal, TEXT I buf, VARDET AV var |
| SKRIV_NL literal | SkrivNyRad med bara ett ord (inte TEXT/VARDET) fungerar nu |
| Raw Skriv | Tokenizern emitterar hela raden som en token — nyckelord i strängar fungerar |
| Data-epilog | .data-sektionen emitteras alltid, program behöver inte ha JagMåsteGåNu |
| B4 | FOR-loop i pipeline-parsern |
| Blank lines | Compiler fix: Läs till X hoppar över tomma rader (skippar inte vid EOF) |
| Inkludera-flytt | Inkludera-hantering flyttad från emit_word till check_skriv (rad-nivå) |
| JAMFOR buf-namn | JAMFOR-handleren sparar buffertnamnet korrekt (hårdkodad input_buf åtgärdad) |
| skriv_handled_buf | Deklarerad i data-sektionen (saknades tidigare) |

---

## Verifieringsplan

1. ✅ 31/31 pipeline-tester gröna
2. `hiuh-tokenizer.exe < src/hiuh-parser.hiuh | hiuh-parser.exe > parser2.s`
   Assemblera + länka → kör pipeline-tester med parser2.exe, alla gröna
3. `hiuh-tokenizer.exe < src/hiuh-tokenizer.hiuh | hiuh-parser.exe > tokenizer2.s`
   Assemblera → `tokenizer2.exe < src/test-arith-parser.hiuh | hiuh-parser.exe`
   ska ge samma output som original-tokenizern
4. Sluttest (fixpunkt): parser2.s == parser3.s
