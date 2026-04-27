# Parser plan

## Goal

Write hiuh-parser.hiuh — reads the token stream from hiuh-tokenizer,
emits x86-64 Windows assembly directly to stdout.

Pipeline: hiuh-tokenizer.exe < source.hiuh | hiuh-parser.exe > out.s
Then: as + ld to produce the final executable.

---

## Compiler additions needed first

### 1. KopieraBuffer (buffer copy) — BLOCKING

The parser reads each token into källa via Läs, then must save it
before the next Läs. Without a copy instruction every save is ~8 lines:

    För j från 0 till 255
        Sätt b till tecken j ur källa
        Lagra b vid j i tok_buf
        Om b är 0
            Bryt
        Hejdå
    Hejdå

Proposed syntax:  KopieraBuffer tok_buf från källa
Tokenizes to:     ('COPY_BUF', dest, src)
Compiles to:      call strcpy (Windows) / inline byte loop (Linux)

This is needed constantly — every Läs call requires a save.

### 2. Medan (while loop) — NICE TO HAVE

The main read loop uses För _ från 0 till 9999 + Bryt which works
but wastes 9999 iterations and reads unintuatively. A while loop:

    Medan las_ok är 1
        Läs till las_ok
        ...
    Hejdå

Requires: READ returning a result variable (Läs till X), and
a new loop construct that checks a condition each iteration.
Can defer this — the För _ + Bryt pattern works fine for now.

### 3. Register budget — POTENTIAL BLOCKER

Parser needs these named variables:
    state    — current parse state (what token are we expecting?)
    lbl_cnt  — label counter for emitting unique loop/if labels
    reg_next — next GP register index to allocate
    depth    — loop/if nesting depth (for label stack)
    träff    — comparison result (from Sätt träff till Jämför)
    i        — inner loop counter (buffer copy, symbol table scan)

That is exactly 6 — the maximum. No room for anything extra.

If a 7th is needed, options:
  A. Add %rbp as a 7th GP variable register (callee-saved, unused now)
  B. Encode two small values into one register (pack state + depth)
  C. Spill one variable to a named buffer (read/write memory instead)

Option A is cleanest. Add %rbp to reg_names in hiuh-native.py.
Note: %rbp must be saved/restored in the function prologue/epilogue
(already done for callee-saved regs in the current prologue? check.)

---

## Parser design

### State machine

The parser is a single-pass state machine. One variable (state)
tracks what token is expected next:

    0  = idle, waiting for statement-opening keyword
    1  = saw SET, waiting for variable name
    2  = saw SET + varname, waiting for TILL
    3  = saw SET + varname + TILL, waiting for value
    4  = saw FOR, waiting for loop variable
    5  = saw FOR + var, waiting for FRAN
    6  = saw FOR + var + FRAN, waiting for start value
    7  = saw FOR + var + FRAN + start, waiting for TILL
    8  = saw FOR + var + FRAN + start + TILL, waiting for end value
    9  = saw IF, waiting for variable (condition LHS)
    10 = saw IF + var, waiting for AR
    11 = saw IF + var + AR, waiting for value or MINDRE/STORRE
    ... etc.

### Symbol table

6 named buffers hold variable names in allocation order:
    vname0, vname1, vname2, vname3, vname4, vname5

reg_next tracks how many have been allocated (0-5).

Lookup: scan vname0..vname(reg_next-1) with JämförBuffer.
First match index → register name (%r12/%r13/%r8/%r9/%r10/%r11).

Register index to name:
    Om reg_idx är 0 → Skriv %r12
    Om reg_idx är 1 → Skriv %r13
    Om reg_idx är 2 → Skriv %r8
    Om reg_idx är 3 → Skriv %r9
    Om reg_idx är 4 → Skriv %r10
    Om reg_idx är 5 → Skriv %r11

### Token buffers

    tok_buf   — current token (copy of källa after each Läs)
    var_buf   — variable name being parsed in current statement
    val_buf   — value operand being parsed
    var2_buf  — second variable (for binary ops like PLUS)

### Label emission

    lbl_cnt starts at 0, incremented for each loop/if.
    Loop start: Skriv .L + SkrivNyRad värdet av lbl_cnt
    Loop end label stored as integer in depth stack.

    Problem: parser needs a stack of pending label numbers
    (one per nesting level) to emit matching END labels.
    With depth as a single integer and lbl_cnt as a counter,
    we need a way to store "label N belongs to depth D".

    Simple approach for first version: only support flat programs
    (no nested FOR/IF). Depth tracking can be added later.
    This still handles most real HIUH programs.

### Assembly output format

Preamble (emitted once at start):
    .text
    .globl main
    main:
    push %rbp
    ... etc (copy current Python compiler prologue)

Per statement:
    SET x 0    →  mov $0, %r12
    FOR i 0 N  →  mov $0, %r10 / .LN: / cmp ... / jge .LM / ... / inc %r10 / jmp .LN / .LM:
    IF x AR 0  →  cmp $0, %r12 / je .LN (or jne)
    END        →  close current block (emit label or inc)
    SKRIV_NL X →  lea msgN(%rip), %rcx / call puts
    EXIT       →  mov $0, %ecx / call exit

Data section (emitted at end):
    .data
    fmt_int: .asciz "%lld\n"
    input_buf: .skip 256
    ... any string literals encountered

---

## Implementation order

1. Add KopieraBuf to hiuh-native.py (tokenizer + parser + compile)
2. Optionally add %rbp as 7th register if budget is tight
3. Write hiuh-parser.hiuh starting with SET and SKRIV_NL only
4. Test: echo "SET x TILL 5\nSKRIV_NL x" | hiuh-parser.exe → valid .s
5. Add FOR support (flat, no nesting)
6. Add IF support (flat)
7. Add END support
8. Test: tokenize + parse a simple HIUH program end-to-end
9. Iterate — add remaining opcodes as needed

---

## Current state

Compiler:    native/hiuh-native.py  (Windows + Linux targets)
Tokenizer:   hiuh-tokenizer.hiuh    (multi-line, 27 keywords, self-tokenizes to 668 tokens)
Branch:      master
Working:     FOR, IF/ELSE, SET, PLUS, READ, Skriv/SkrivNyRad,
             Lagra/tecken, Jämför/JämförBuffer (explicit var),
             Bryt, JagMåsteGåNu, För _ (anonymous counter),
             Sätt x till Y är mindre/större än Z
