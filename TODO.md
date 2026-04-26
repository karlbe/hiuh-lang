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

### Medium prioritet  
- [ ] Tokenizer: bygg ord genom att jämföra med mellanslag (32)
- [ ] Lagra tokens i en lista

### Lower prioritet
- [ ] Självkompilering: HIUH kompilerar HIUH

## Test-kommandon
```bash
# Testa tokenizer
python3 native/hiuh-native.py hiuh-tokenizer.hiuh /tmp/test && printf "Hej" | /tmp/test
```

## Senaste commits
- 5672cfe: Fix: FOR parser now handles nested IF-ELSE properly
- 6b23a8c: Add TODO.md for self-compilation goal
- 97fb922: WIP: tokenizer with char comparison
