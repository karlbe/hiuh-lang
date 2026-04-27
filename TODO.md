# HIUH Självkompilering - TODO

## Mål
- [ ] HIUH kompilator skriven i HIUH som kan kompilera sig själv

## Arkitektur
1. **Tokenizer** - dela input i ord (ord-gränser vid mellanslag)
2. **Parser** - bygg tokens till statements  
3. **Kodgenerator** - generera x86_64 assembly

## Status

### Python-kompilatorn (native/hiuh-native.py) - KLAR
- [x] Tokenizer - fungerar i Python
- [x] Parser - fungerar
- [x] Kodgenerator - genererar x86_64 assembly
- [x] Funktioner (lambda-style)
- [x] IF-ELSE i loopar
- [x] Nästlade loopar

### HIUH tokenizer (hiuh-tokenizer.hiuh) - INTE KLAR
- [ ] **VIKTIGT:** hiuh-tokenizer.hiuh är bara en TECKENRÄKNARE, inte en riktig tokenizer!
- [ ] För att bli självkompilerande behövs:
  1. **Strings** - lagra källkod
  2. **Listor** - spara tokens
  3. **Riktig tokenisering** - dela kod i tokens som Python-tokenizern

## Nästa steg (prioriterad ordning)

### 1. String-stöd i HIUH
- [ ] Kunna lagra text i variabler
- [ ] Jämföra tecken (==, !=)
- [ ] Input via Läs

### 2. List-stöd i HIUH
- [ ] Kunna skapa lista
- [ ] Kunna lägga till element
- [ ] Kunna hämta element (index)

### 3. Riktig tokenizer i HIUH
- [ ] Läs HIUH-kod från input
- [ ] Dela i ord (mellanslag = gräns)
- [ ] Returnera lista av tokens

## Kända buggar
- Hejdå i IF-body bryter inte FOR-loopen
- Output är ~128 för alla inputs (karaktärs-räknare, inte tokenizer)

## Test-kommandon
```bash
# Testa tokenizer (Python)
python3 native/hiuh-native.py hiuh-tokenizer.hiuh /tmp/test && printf "Hej" | /tmp/test

# Testa ord_lista för självkompilering
python3 native/hiuh-native.py --ord-lista hiuh-tokenizer.hiuh
```

## Senaste commits
- 4a77fd2: Tokenizer: HIUH tokenizer with character-by-character analysis
- 2a637d5: Fix: SKRIV_VAR byte handling and register allocation
