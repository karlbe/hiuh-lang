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

### Medium prioritet  
- [x] Stöd för `x är y` i tokenizer → SET (58a596c)
- [ ] Tokenizer: bygg ord genom att jämföra med mellanslag (32)
- [ ] Lagra tokens i en lista
- [ ] **Funktionstyper**: `Sätt <namn> till grej med x, y` för att skapa funktioner (delvis fixat)
- [x] Stöd för `x är y pluss z` i tokenizer (adb13ef)

### Lower prioritet
- [ ] Självkompilering: HIUH kompilerar HIUH
- [ ] Fler register för FOR-loop variabler (spill till minne)

## Test-kommandon
```bash
# Testa tokenizer
python3 native/hiuh-native.py hiuh-tokenizer.hiuh /tmp/test && printf "Hej" | /tmp/test
# Testa Fibonacci (iterativ)
cat > /tmp/fibo.hiuh << 'EOF'
Sätt a till 0
Sätt b till 1
För i från 0 till 5
    Sätt temp till b
    b är a pluss b
    a är temp
Hejdå
Skriv värdet av a
EOF
python3 native/hiuh-native.py /tmp/fibo.hiuh /tmp/fibo && printf "" | /tmp/fibo | od -c
```

## Senaste commits
- 5672cfe: Fix: FOR parser now handles nested IF-ELSE properly
- 6b23a8c: Add TODO.md for self-compilation goal
- 97fb922: WIP: tokenizer with char comparison
