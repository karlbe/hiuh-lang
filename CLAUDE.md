# HIUH — Claude Code Notes

## Compiling HIUH programs

Run from the `native\` directory (that's where `hiuh.cfg` is found).
The source file path can be relative or absolute.

```
cd native
python hiuh-native.py ../source.hiuh [output.exe]
```

The assembler and linker paths are in `native/hiuh.cfg`:
- as: `G:\msys64\mingw64\bin\as.exe`
- ld: `G:\msys64\mingw64\bin\ld.exe`

The compiler auto-detects Windows (`sys.platform == 'win32'`) so no
`--windows` flag is needed when running on this machine.

To view generated assembly without compiling:
```
python native/hiuh-native.py --asm <source.hiuh>
```

## Pipeline (tokenizer → parser)

```
native/hiuh-tokenizer.exe < source.hiuh | native/hiuh-parser.exe > out.s
```

Then assemble and link manually if needed:
```
G:\msys64\mingw64\bin\as.exe -o out.o out.s
G:\msys64\mingw64\bin\ld.exe -o out.exe out.o -lmingw32 -lmsvcrt -lkernel32
```

## Key files

| File | Purpose |
|---|---|
| `native/hiuh-native.py` | Python compiler (source of truth) |
| `hiuh-tokenizer.hiuh` | Tokenizer written in HIUH |
| `hiuh-parser.hiuh` | Parser written in HIUH (in progress) |
| `DESIGN.md` | Language design decisions |
| `TODO.md` | Implementation tasks |

## Writing HIUH code — lessons learned

### Sequential Om blocks cascade — they are NOT if/else-if

All `Om` blocks in the same scope evaluate independently in a single pass.
If block N changes the variable being tested, block N+1 may unexpectedly match.

**Wrong** (state 0 transitions to state 1, then the state-1 block also fires):
```
Om state är 0
    Sätt state till 1
Hejdå
Om state är 1        ← also runs, because state is now 1
    ...
Hejdå
```

**Correct — use a `done` flag**:
```
Sätt done till 0
Om done är 0
    Om state är 0
        Sätt state till 1
        Sätt done till 1
    Hejdå
Hejdå
Om done är 0
    Om state är 1
        ...
        Sätt done till 1
    Hejdå
Hejdå
```

**Correct — use a function with early `ge` returns**:
```
Funktion dispatch med idx
    Om idx är 0
        . do thing for 0
        ge 0
    Hejdå
    Om idx är 1
        . do thing for 1
        ge 0
    Hejdå
    ge 0
Hejdå
```
Once `ge` executes the function returns and no further `Om` blocks run.

### Functions with early `ge` returns are the safe case-dispatch pattern

Whenever you need to do different things based on a value (like dispatching on a slot index or register index), put each case in a function with an early `ge`. This is safer than sequential `Om` blocks because the function exits on the first match. See `alloc-slot.hiuh` and `skriv-reg.hiuh` for examples.

### Maximum 7 variables per scope

The compiler allocates: `%r12, %r13, %r8, %r9, %r10, %r11, %rbp` (in that order).
Plan your variable names before writing code — exceeding 7 is a compile error.
Functions have their own separate scope (their own 7 slots).

### Caller-saved registers (%r8–%r11) are clobbered by `Läs`

Variables allocated to `%r8`–`%r11` (slots 2–5) are NOT preserved across a `Läs` call,
because `Läs` calls Windows API functions (`__acrt_iob_func`, `fgets`) that follow the
Windows x64 ABI and freely clobber those registers. The compiler wraps these calls with
`win_call_save`/`win_call_restore`, but be aware of this when debugging unexpected value
loss after a `Läs`.

### Use `Inkludera` to unit-test components independently

Write each function in its own `.hiuh` file, then write a small test harness that
`Inkludera`s just that file and exercises it. Verify the component works before
including it in the larger program. Example files: `hitta-var.hiuh`, `alloc-slot.hiuh`,
`skriv-reg.hiuh`, each with corresponding `test-*.hiuh` test programs.

### `done` flag pattern for state machines in `Sålänge` loops

```
Sålänge condition
    Sätt done till 0
    Om done är 0
        Om state är 0
            . handle state 0
            Sätt state till 1
            Sätt done till 1
        Hejdå
    Hejdå
    Om done är 0
        Om state är 1
            . handle state 1
            Sätt done till 1
        Hejdå
    Hejdå
    Läs till condition
Hejdå
```

The outer `Om done är 0` ensures only one state block fires per loop iteration.
Reset `done` to 0 at the top of every iteration.
