# HIUH Självkompilering - TODO

## Mål
- [ ] HIUH kompilator skriven i HIUH som kan kompilera sig själv

## Status

### Tokenizer (hiuh-tokenizer.hiuh) - KLAR
- [x] Tokenizer fungerar korrekt
- [x] Output: `SET\nx\nTILL\n5\n4` (token per rad + count)
- [x] Multiline input stöds
- [x] 27 nyckelord: SET, FOR, IF, ELSE, END, READ, SKRIV_NL, SKRIV, LAGRA, JAMFOR, JAMFOR_BUF, EXIT, BREAK, TILL, FRAN, AR, PLUS, UR, VID, MED, TECKEN, AN, MINDRE, STORRE, VARDET, AV, TEXT, I, GE

### Native kompilator (native/hiuh-native.py) - KLAR
- [x] Windows x64 assembly output
- [x] KopieraBuffer (buffer copy)
- [x] Sålänge (while loop)
- [x] 7 register (%r12-%r11, %rbp)
- [x] Verkliga funktionsanrop (call/ret)
- [x] Rekursion stöds (test-rekursion.exe)

### Parser i HIUH (hiuh-parser.hiuh) - NÄSTA STEG
- [ ] Måste skrivas för att kunna kompilera sig själv

## Vägen till självkompilering

### Steg 1: hiuh-parser.hiuh (BLOCKERANDE)
Läser tokenström från hiuh-tokenizer.exe, skriver x86_64 assembly till stdout.

Pipeline: `hiuh-tokenizer.exe < source.hiuh | hiuh-parser.exe > out.s`

Kräver:
- Läs token från stdin (en token per rad, t.ex. "SET", "x", "TILL", "5")
- State machine för SET, FOR, IF, ELSE, END, SKRIV_NL, EXIT
- Symboltabell (6 variabler: vname0..vname5 → %r12-%r11)
- Labelhantering för loopar och if-blocks
- Assembler-output till stdout

### Steg 2: Bygg ut parser
- Läs-tokens: READ, CHAR_AT (tecken X ur källa)
- Aritmetik: PLUS, MINUS, GÅNGER, DELAT
- Jämförelser: AR, MINDRE, STORRE, LIKA, OLIKA
- Nästlade loopar och if-satser
- KopieraBuffer (används flitigt för att spara tokens)

### Steg 3: Självkompilering
1. hiuh-native.py kompilerar hiuh-parser.hiuh → hiuh-parser.exe
2. hiuh-parser.exe kompilerar hiuh-tokenizer.hiuh → tokenizer.exe (samma som Python-versionen)
3.Verifiera: båda tokenizerarna ger samma output

## Tokenizer output-format

```
SET              # keyword
x                # variable name
TILL             # keyword
5                # value
4                # total token count
```

## Assembler-output format (preliminärt)

```asm
.text
.globl main
main:
    push %rbp
    mov %rsp, %rbp
    # ... program code ...

# Data section
.data
fmt_int: .asciz "%lld\n"
```

Per statement:
- SET x TILL 5    →  mov $5, %r12  (allocate x if needed)
- FOR i 0 10      →  mov $0, %r10 / .L0: / cmp $10, %r10 / jge .L1 / ... / inc %r10 / jmp .L0 / .L1:
- IF x AR 0       →  cmp $0, %r12 / je .L2
- SKRIV x         →  lea fmt_int(%rip), %rcx / mov %r12, %rdx / call printf
- EXIT 0          →  xor %ecx, %ecx / call exit
