# HIUH Självkompilering - TODO

## Mål
Kompilator skriven i HIUH som kan kompilera sig själv.
Pipeline: `hiuh-tokenizer.exe < source.hiuh | hiuh-parser.exe > out.s`

---

## Status

### Tokenizer (src/hiuh-tokenizer.hiuh) — KLAR
Läser tecken från stdin, skriver ett token per rad till stdout.
Tokens: SET FOR IF ELSE END READ SKRIV_NL SKRIV LAGRA JAMFOR JAMFOR_BUF
        EXIT BREAK TILL FRAN AR PLUS MINUS UR VID MED TECKEN AN MINDRE STORRE
        VARDET AV TEXT I GE  + identifierare/literaler

### Kompilator (compiler/hiuh-native.py) — KLAR
- [x] Windows x64 assembly
- [x] Text-typ med automatisk buffertallokering (_text_N)
- [x] Typinferens och typkontroll (Heltal / Text)
- [x] Text-argument till funktioner (TextPtr)
- [x] Inkludera (preprocessor med cykeldetektion)
- [x] Verkliga funktionsanrop med call/ret, rekursion

### Parser (src/hiuh-parser.hiuh) — PÅGÅR
Hanterar just nu: SET (literal, VARDET AV, PLUS, MINUS, JAMFOR), SKRIV_NL (VARDET AV, TEXT I),
OKA, MINSKA, IF/END, SALANGES/END, BREAK, MINDRE AN, STORRE AN, READ, EXIT
Testat och verifierat med test.py (19/19 gröna).

---

## Språkfunktioner att lägga till i kompilatorn INNAN självkompilering

### ~~1. minus — subtraction~~ — KLAR
`Sätt x till a minus b` — implementerad i hiuh-native.py.

### ~~2. Fixa `Om x är texten Y`~~ — KLAR
`Om tok är texten SET` och `Sålänge tok är texten X` fungerar nu korrekt.
Token-dispatch med early-`ge` per tokentyp är nu möjlig utan `done`-flagga.

### ~~3. Sålänge med texten~~ — KLAR (fixat samtidigt som #2)

### ~~4. SkrivHeltal / inline integer printing~~ — KLAR via `och`
`SkrivNyRad jne L och label_nr` skriver `jne L42\n` på en rad.
`SkrivNyRad L och label_nr och :` skriver `L42:\n`.
Implementerat: ` och ` i Skriv/SkrivNyRad delar upp i delar — variabler skrivs
som värde, övriga delar som literaler. Avblockerar labelgenerering i Fas 2.

### ~~4b. `Om A och B` — sammansatta villkor~~ — KLAR
`Om done är 0 och state är 4` kompilerar till chained CMP + jz. Sparar ett
nästlingsdjup och en `Hejdå` per block.

### ~~5. `Öka x` / `Minska x` — räknarshorthand~~ — KLAR
`Öka label_nr` kompileras till `label_nr = label_nr + 1`. Fungerar överallt.

### ~~6. `Skriv ... och text i buf och ...`~~ — KLAR
`SkrivNyRad prefix och text i input_buf och suffix` fungerar.
Parsern kan nu emittera `mov $<värde>, %r12` på en rad:
`SkrivNyRad     mov $ och text i input_buf och , %r12`

### ~~7. `Läs till x` ger Text, `inte är` för negation~~ — KLAR
`Läs till rad` gör `rad` till en Text-variabel med radens innehåll.
EOF sätter `rad` till tom sträng. Loop-mönster:
```
Läs till rad
Sålänge rad inte är texten
    SkrivNyRad värdet av rad
    Läs till rad
Hejdå
```
`inte är` fungerar i både `Om` och `Sålänge`, för text och heltal.
`input_buf` och integer-flaggan behövs inte längre.

### 8. Parser-omskrivning med funktionsdispatch (nu avblockerad)
Nu när `Om tok är texten X` fungerar kan hela state-maskinen i hiuh-parser.hiuh
ersättas med en dispatchfunktion med early-`ge` per tokentyp.
SET-hanteraren kan kalla `Läs` tre gånger internt — ingen state 1/2/3 behövs.
Gör parsern ~50% kortare och läsbar.

---

## Parser-features att implementera (src/hiuh-parser.hiuh)

Varje token-typ nedan behöver en handler i parsern.
Använd funktions-dispatch med early-ge (se ovan) istället för
done-flagga state machine.

### Fas 1 — Grundläggande uttryck
- [x] PLUS / MINUS → `mov src, dst / add src2, dst` eller `sub`
- [x] SET VARDET AV → variabelkopiering `mov %rSRC, %rDST`
- [x] OKA / MINSKA → `inc %rXX` / `dec %rXX`
- [x] READ → fgets + newline-strip till input_buf

### Fas 2 — Kontrollflöde
Labelgenerering via `label_buf[0]` byte-räknare + `SkrivNyRad jne L och label_nr`.

- [x] IF var AR val → `cmp $N, %rXX / jne L{n}` (literal och variabel)
- [x] END (för IF) → emit `L{n}:`
- [x] SALANGES var AR val → `L{n}: cmp / jne L{n+1}` + spara båda
- [x] END (för SALANGES) → `jmp L{n} / L{n+1}:`
- [x] BREAK → `jmp L{loop_end}`
- [x] MINDRE AN / STORRE AN → `jge` / `jle` varianter av IF och SALANGES

OBS: IF/SALANGES stödjer EJ nästling — single-level only.
Nästling kräver label-stack i buffer (implementeras vid behov).

### Fas 3 — Stränghantering
- [x] JAMFOR buf MED lit → strcmp → result i variabel (1=match, 0=no match)
- [x] SKRIV_NL TEXT I buf → puts(input_buf)
- [ ] LAGRA char VID idx I buf → store byte (`movb $N, offset(%rip)`)
- [ ] TECKEN idx UR buf → load byte (`movzbq offset(%rip), %rDST`)
- [ ] JAMFOR_BUF buf1 MED buf2 → strcmp två buffertar
- [ ] KopieraBuffer buf1 TILL buf2 → strcpy

### Fas 4 — Funktioner
- [ ] FUNC_DEF name params → function prologue + param-register-mapping
- [ ] GE val → return + epilogue
- [ ] ANROPA func args → call med argument-setup

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
