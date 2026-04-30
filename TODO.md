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

## Aktiva buggar — tokenizer2.exe hänger

### Bug C1: `Sätt x till y` (variabel-till-variabel-kopia) saknas i parsern
**Symptom:** `Sätt klar till i_ord` i FOR-loopen genererar tom kod. `klar` sätts
aldrig till 1 vid ordgräns → `Om klar är 1`-blocket (emit_word) anropas aldrig
mitt i raden. Hela radens innehåll hamnar i ett enda token.

**Fix:** Lägg till hantering i SET-handleren (hiuh-parser.hiuh): om token efter
TILL varken är VARDET, JAMFOR, TECKEN, PLUS, MINUS — är det en variabelkopia.
Slå upp källvariabeln med hitta_var, emittera `mov %rSRC, %rDST`.

### Bug C2: JAMFOR-literaler tokeniseras vid självkompilering (bootstrapping-problem)
**Symptom:** I check_skriv jämförs `ord_buf` mot `"SKRIV_NL"` och `"SKRIV"` (token-
formerna), inte mot `"SkrivNyRad"` och `"Skriv"`. Vid självtokenisering konverteras
de svenska nyckelorden i `Jämför ord_buf med SkrivNyRad` till sina tokenformer, så
check_skriv känner aldrig igen en Skriv/SkrivNyRad-rad.

**Lösning:** Skriv om check_skriv i hiuh-tokenizer.hiuh att detektera "Skriv"/
"SkrivNyRad" med teckenkodsjämförelser istället för Jämför:
- Kontrollera att ord_buf[0]=='S'(83), ord_buf[1]=='k'(107), ord_buf[4]=='v'(118)
- ord_buf[5]==0 → Skriv; ord_buf[5]=='N'(78) → SkrivNyRad
- Använder befintliga variabler (ch räcker, 6 av 7 slots används redan)
- "Inkludera" är INTE ett HIUH-nyckelord → överlever tokenisering som-är ✓

### Bug C3: Möjlig infinite loop i tokenizer2.exe (okänd plats)
Ovanstående buggar förklarar fel output men inte nödvändigtvis en hängning.
Hängningsplatsen är ännu inte exakt identifierad. Nästa steg: sätt breakpoints
eller lägg till debugutskrifter för att avgränsa var loopen sitter.

**Kandidater:**
- check_skriv whitespace-skip-loop (L133/L135 i tokenizer2.s rad ~1774):
  loopar tills `ch > 32`, men triggas bara om Inkludera matchar — borde inte
  vara problemet för vanlig input
- Något i huvud-Sålänge-loopen som inte avslutar korrekt vid EOF
- emit_word anropas med en buffer som aldrig termineras med null

---

## Nästa steg (i prioritetsordning)

1. **Fixa C1** (variabelkopia i parsern) — enkel parser-fix, påverkar många program
2. **Fixa C2** (teckenkods-check i tokenizern) — kräver omskrivning av check_skriv
3. **Lokalisera C3** — om hängningen kvarstår efter C1+C2, debugga tokenizer2.s
4. **B5: LAS_FIL i parsern** — krävs för att tokenizern ska kunna inkludera filer
5. **Verifiera 31/31 pipeline-tester** efter varje fix

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
