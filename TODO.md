# HIUH Självkompilering - TODO

## Mål
Kompilator skriven i HIUH som kan kompilera sig själv.
Pipeline: `hiuh-tokenizer.exe < source.hiuh | hiuh-parser.exe > out.s`

---

## Status

### Tokenizer (src/hiuh-tokenizer.hiuh) — KLAR
Läser tecken från stdin, skriver ett token per rad till stdout.
Tokens: SET FOR IF ELSE END READ SKRIV_NL SKRIV LAGRA JAMFOR JAMFOR_BUF
        EXIT BREAK TILL FRAN AR PLUS UR VID MED TECKEN AN MINDRE STORRE
        VARDET AV TEXT I GE  + identifierare/literaler

### Kompilator (compiler/hiuh-native.py) — KLAR
- [x] Windows x64 assembly
- [x] Text-typ med automatisk buffertallokering (_text_N)
- [x] Typinferens och typkontroll (Heltal / Text)
- [x] Text-argument till funktioner (TextPtr)
- [x] Inkludera (preprocessor med cykeldetektion)
- [x] Verkliga funktionsanrop med call/ret, rekursion

### Parser (src/hiuh-parser.hiuh) — PÅGÅR
Hanterar just nu: SET, SKRIV_NL (värdet av), EXIT
Allt nedan behöver läggas till.

---

## Språkfunktioner att lägga till i kompilatorn INNAN självkompilering

### 1. minus — subtraction (BLOCKERANDE)
`Sätt x till a minus b`
Behövs för: minska labelräknare, beräkna offsets.

### 2. Fixa `Om x är texten Y` (BLOCKERANDE för ren arkitektur)
Just nu tar `Om`-tokenizern bara sista ordet som var2 — `Om tok är texten SET`
jämför mot `SET` istället för `texten SET`.

Fixa: i Om-grenen, om orden efter `är` börjar med `texten`, ta hela frasen.

**Varför kritiskt:** Med denna fix kan hela token-dispatch skrivas som
en funktion med early-ge per tokentyp — ingen `done`-flagga behövs:

```
Funktion hantera med tok är Text
    Om tok är texten SET
        . hantera SET
        ge 0
    Hejdå
    Om tok är texten IF
        . hantera IF
        ge 0
    Hejdå
    ge 0
Hejdå
```

Det minskar parserns storlek drastiskt.

### 3. Sålänge med texten (trevligt att ha)
`Sålänge tok är texten VARDET`
Samma fix som Om ovan, i Sålänge-grenen.

---

## Parser-features att implementera (src/hiuh-parser.hiuh)

Varje token-typ nedan behöver en handler i parsern.
Använd funktions-dispatch med early-ge (se ovan) istället för
done-flagga state machine.

### Fas 1 — Grundläggande uttryck
- [ ] PLUS a b → `mov a, %rcx / add b, %rcx / mov %rcx, %rNN`
- [ ] SKRIV_NL literal → `call puts` (nuvarande text i input_buf)
- [ ] SKRIV literal / SKRIV VARDET → printf utan newline
- [ ] READ → fgets + newline-strip till input_buf

### Fas 2 — Kontrollflöde (kräver labelgenerering)
Labelgenerering: `Skriv L` + `Skriv värdet av label_nr` — fungerar redan
med befintliga Skriv + Heltal-utskrift.

- [ ] IF var AR val → `cmp / je L{n}` + spara n i variabel
- [ ] END (för IF) → emit `L{n}:` från sparad variabel
- [ ] WHILE var AR val → `L{n}: / cmp / jne L{n+1}` + spara båda
- [ ] END (för WHILE) → `jmp L{n} / L{n+1}:`
- [ ] SMALLER/LARGER (MINDRE/STORRE AN) → setl/setg varianter
- [ ] ELSE → jmp förbi else-block + emit if-end label

Nästlingsdjup: hantera 2 nivåer med label0/label1 + depth-räknare.
FOR (För) kan skippas i fas 1 — tokenizern och parsern undviker det.

### Fas 3 — Stränghantering
- [ ] JAMFOR buf med lit → strcmp → result i variabel
- [ ] LAGRA char vid idx i buf → store byte
- [ ] JAMFOR_BUF buf1 med buf2

### Fas 4 — Funktioner
- [ ] FUNC_DEF name params → function prologue + param-register
- [ ] GE val → return + epilogue
- [ ] ANROPA func args → call med argument

---

## Verifieringsplan

1. `python compiler/hiuh-native.py src/hiuh-tokenizer.hiuh tokenizer.exe`
   `python compiler/hiuh-native.py src/hiuh-parser.hiuh parser.exe`

2. Testa med enkelt program:
   `tokenizer.exe < src/test-parser2.hiuh | parser.exe > out.s`
   Assemblera + länka + kör → verifiera output matchar Python-kompilatorns.

3. Testa med tokenizern själv:
   `tokenizer.exe < src/hiuh-tokenizer.hiuh | parser.exe > tokenizer2.s`
   Assemblera → `tokenizer2.exe < src/test-parser2.hiuh` ska ge samma output som `tokenizer.exe`.

4. Sluttest — kompilera parsern med sig själv:
   `tokenizer.exe < src/hiuh-parser.hiuh | parser.exe > parser2.s`
   `tokenizer.exe < src/hiuh-parser.hiuh | parser2.exe > parser3.s`
   parser2.s och parser3.s ska vara identiska.
