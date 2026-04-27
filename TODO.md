# HIUH Självkompilering - TODO

## Mål
- [ ] HIUH kompilator skriven i HIUH som kan kompilera sig själv

## Överblick Architecture
1. **Tokenizer** - dela input i ord (ord-gränser vid mellanslag)
2. **Parser** - bygg tokens till statements
3. **Kodgenerator** - generera x86_64 assembly

## TODO - Fixa buggar

### Hög prioritet (FIXAT!)
- [x] IF-ELSE i FOR fungerar nu! (commit 5672cfe)
- [x] CMP_LT genererar nu korrekt assembly (5672cfe)
- [x] Register-konflikt: r14/r15 reserverade för stack/tecken (4da9973)
- [x] IF-ELSE i funktioner fungerar nu! (ab98ccd)
- [x] Fibonacci loop ger rätt svar! (56a82a9 - %4 → %6)
- [x] **SKRIV_VAR fungerar nu** - fixade byte-register hantering (2a637d5)
- [x] **CHAR_AT i variabel** - ny SET_CHAR_AT hantering (2a637d5)

### Medium prioritet  
- [x] Tokenizer: bygg ord genom att jämföra med mellanslag (32)
- [x] Lagra tokens i en lista - tokenizer returnerar nu (tokens, ord_lista)
- [x] Funktionstyper: `Sätt <namn> till grej med x, y` för att skapa funktioner
- [x] Stöd för `x är y` i tokenizer → SET (58a596c)
- [x] Stöd för `x är y pluss z` i tokenizer (adb13ef)

### Tokenizer (KLART!)
- [x] **Tokenizer fungerar** - hiuh-tokenizer.hiuh kompilerar och kör
- [x] Räknar tecken i text (approx 128 tecken output pga loop-implementation)
- [x] ord_lista genereras med 113 ord för självkompilering
- [x] Fixat hiuh.cfg med korrekta Linux-sökvägar (/usr/bin/as, /usr/bin/ld)

## Lower prioritet
- [ ] Självkompilering: HIUH kompilerar HIUH

## Test-kommandon
```bash
# Testa tokenizer
python3 native/hiuh-native.py hiuh-tokenizer.hiuh /tmp/test && printf "Hej" | /tmp/test

# Testa ord_lista för självkompilering
python3 native/hiuh-native.py --ord-lista hiuh-tokenizer.hiuh
```

## Kända buggar
- Output är ~128 för alla inputs (loop räknar positioner, inte ord korrekt)
- Hejdå i IF-body bryter inte FOR-loopen (behöver språk-stöd för nested breaks)

## Senaste commits
- 4a77fd2: Tokenizer: HIUH tokenizer with character-by-character analysis
- 2a637d5: Fix: SKRIV_VAR byte handling and register allocation
- aa53827: Update TODO: mark fixes for SKRIV_VAR, SET_CHAR_AT
- 56a82a9: Fix: modulo was %4 but reg_names has 6 entries - caused overflow
- ab98ccd: Fix: IF-ELSE handling in parser and compiler
- d761e3f: Fix: expanded register pool from 2 to 4 registers - fixes Fibonacci loop