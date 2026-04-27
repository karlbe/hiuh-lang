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
- [x] **IF-ELSE i funktioner fungerar nu!** (commit ab98ccd)
  - ELSE body kompilerades inte tidigare - nu fixat
  - RETURN i IF/ELSE body fungerar

### Medium prioritet  
- [x] Stöd för `x är y` i tokenizer → SET (58a596c)
- [ ] Tokenizer: bygg ord genom att jämföra med mellanslag (32)
- [ ] Lagra tokens i en lista
- [x] **Funktionstyper**: `Sätt <namn> till grej med x, y` för att skapa funktioner
- [x] Stöd för `x är y pluss z` i tokenizer (adb13ef)

## Kända buggar
- [x] Fibonacci loop ger 0 istället för 5 (d761e3f - expanded register pool)
- [x] Funktioner returnerar fel värde (r14 allokering fixad)

## Test-kommandon
```bash
# Testa tokenizer
python3 native/hiuh-native.py hiuh-tokenizer.hiuh /tmp/test && printf "Hej" | /tmp/test
# Testa Fibonacci (iterativ) - FIXAT!
python3 native/hiuh-native.py /tmp/fibo.hiuh /tmp/fibo && printf "" | /tmp/fibo
# Testa funktion (dubbla) - FIXAT!
python3 native/hiuh-native.py /tmp/test-dubbla.hiuh /tmp/test-dubbla && printf "" | /tmp/test-dubbla

## Senaste commits
- ab98ccd: Fix: IF-ELSE handling in parser and compiler
- 3a90cdd: TODO: document known bugs with register allocation and END token
- 58a596c: Fix: tokenizer now handles 'x är y' as SET instead of CMP_EQ
