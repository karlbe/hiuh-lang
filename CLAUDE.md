# HIUH — Claude Code Notes

## Self-hosting philosophy

If a language feature is needed to cleanly self-host (i.e. to write the tokenizer or parser in HIUH itself), add that feature to the language. Do not work around missing features with hacks in the pipeline or compiler. The goal is that the pipeline (tokenizer | parser) can eventually compile itself.

## Compiling HIUH programs

Run from the repo root. `hiuh.cfg` lives next to the compiler in `compiler/`.

```
python compiler/hiuh-native.py src/source.hiuh [output.exe]
```

The assembler and linker paths are in `compiler/hiuh.cfg`:
- as: `G:\msys64\mingw64\bin\as.exe`
- ld: `G:\msys64\mingw64\bin\ld.exe`

The compiler auto-detects Windows (`sys.platform == 'win32'`) so no
`--windows` flag is needed when running on this machine.

To view generated assembly without compiling:
```
python compiler/hiuh-native.py --asm src/source.hiuh
```

## Pipeline (tokenizer → parser)

First compile the tools:
```
python compiler/hiuh-native.py src/hiuh-tokenizer.hiuh hiuh-tokenizer.exe
python compiler/hiuh-native.py src/hiuh-parser.hiuh hiuh-parser.exe
```

Then run the pipeline:
```
hiuh-tokenizer.exe < source.hiuh | hiuh-parser.exe > out.s
```

**IMPORTANT: Always use PowerShell (not Bash) to run .exe files.** The Bash tool uses MSYS2 bash which cannot find .exe files in the current directory. Use the PowerShell tool instead for any command that runs a .exe binary.

**IMPORTANT: PowerShell does not support `<` for stdin redirection.** Use `cmd /c` for pipelines with stdin redirection, but use **full paths** to the .exe files since `cmd /c` does not inherit the current working directory:
```powershell
cmd /c "g:\hiuh-lang\hiuh-tokenizer.exe < src\test.hiuh | g:\hiuh-lang\hiuh-parser.exe > out.s"
```
Or change to the directory first and use relative paths with explicit `.` prefix:
```powershell
cd g:\hiuh-lang; cmd /c ".\hiuh-tokenizer.exe < src\test.hiuh | .\hiuh-parser.exe > out.s"
```
cmd.exe does **not** inherit PowerShell's current working directory — use full paths or `.\exe` with explicit cd in the same statement.

Assemble and link:
```
G:\msys64\mingw64\bin\as.exe -o out.o out.s
G:\msys64\mingw64\bin\ld.exe -o out.exe out.o -lmingw32 -lmsvcrt -lkernel32
```

## Key files

| File | Purpose |
|---|---|
| `compiler/hiuh-native.py` | Python compiler (source of truth) |
| `compiler/hiuh.cfg` | Assembler/linker paths |
| `src/hiuh-tokenizer.hiuh` | Tokenizer written in HIUH |
| `src/hiuh-parser.hiuh` | Parser written in HIUH (in progress) |
| `src/alloc-slot.hiuh` | Parser component: variable slot allocator |
| `src/hitta-var.hiuh` | Parser component: variable lookup |
| `src/skriv-reg.hiuh` | Parser component: register name emitter |
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

### Python compiler: `Sätt x till Jämför buf med pluss/minus` is mis-parsed

In `hiuh-native.py`, the `'pluss' in rest` and `'minus' in rest` checks for arithmetic
must come **after** the `Jämför` check. If they come first, a line like:
```
Sätt träff till Jämför ord_buf med pluss
```
is mis-parsed as arithmetic (rest contains "pluss"), so the comparison is silently dropped.

**Fixed order in the compiler:**
1. `Anropa` (function call with result)
2. `Jämför` / `JämförBuffer` (buffer comparison)
3. `minus` in rest (arithmetic subtraction)
4. `pluss` in rest (arithmetic addition)

### Python compiler: `Skriv` strips trailing spaces

`Skriv     mov` with a trailing space must produce `"mov "` (with space), but the old
parser used `' '.join(words[1:])` which collapsed all whitespace and stripped trailing
spaces. Fixed to extract raw content after the keyword using `.lstrip()` only.

This matters when `Skriv` is used to emit an assembly opcode that must be followed
immediately (no newline) by a register name from a helper function — the space between
opcode and operand must come from the `Skriv` string itself.

### Generated code: Windows API calls clobber %r8–%r11 in the output program

The generated assembly (output of the parser) uses `%r8`–`%r11` for variables in slots
2–5. Any Windows API call in the generated program — including `printf` — clobbers those
registers. Variables stored there are lost across such calls.

**Fix:** wrap printf calls in the generated code with push/pop of all four registers:
```asm
push %r8
push %r9
push %r10
push %r11
subq $32, %rsp        # shadow space for printf
lea fmt_int(%rip), %rcx
mov %rXX, %rdx
call printf
addq $32, %rsp
pop %r11
pop %r10
pop %r9
pop %r8
```
The SKRIV_NL handler in `hiuh-parser.hiuh` now emits this wrapper unconditionally.
Stack alignment is maintained: 4 pushes (32 bytes) + shadow (32 bytes) = 64 bytes, a
multiple of 16.

### `SkrivNyRad` with `och`: each part is `.strip()`ped — trailing spaces in literals are lost

`SkrivNyRad lea  och text i input_buf och (%rip), %rsi` splits on ` och ` giving parts
`["lea", "text i input_buf", "(%rip), %rsi"]` — the trailing space on `"lea "` is stripped,
producing `leainput_buf(%rip), %rsi` (missing space).

**Fix:** Break it into separate `Skriv` calls where the space is a trailing literal:
```
Skriv lea 
Skriv text i input_buf
SkrivNyRad (%rip), %rsi
```
`Skriv lea ` preserves the trailing space (emitted via printf "%s" without stripping).
Only use `och` when no part needs a trailing space — e.g. `jne L och label_nr` is fine.

**Tool limitation:** The Edit tool cannot write trailing spaces — they are silently dropped.
When a `Skriv` line needs a trailing space, use `SPACE` as a placeholder and run
`fix-trailing-spaces.py` afterwards to replace it with a real space:
```
Skriv leaSPACE    . placeholder — run fix-trailing-spaces.py to get "lea "
```
Run: `python fix-trailing-spaces.py src/hiuh-parser.hiuh`

Do NOT use the inline-comment trick (`Skriv lea  .`) — it is a hack that breaks
self-hosting because the dot becomes part of the emitted string in some contexts.

#### PowerShell: use `Select-Object -First N` instead of `head -N`

`head` is not available in PowerShell. Use `Select-Object -First N` to limit output lines.
Wrong: `python test.py | head -50`
Correct: `python test.py | Select-Object -First 50`

**Also applies inside `cmd /c` pipelines** — when using `cmd /c "command | ..."`, do **not** use Unix tools like `head`, `tail`, `sed`, or `grep` in the cmd.exe shell. Either:
1. Pipe the entire output back to PowerShell and filter there, or
2. Use cmd.exe native commands (`findstr`, `more`, `type`) inside the quotes.

Wrong: `cmd /c ".\tokenizer.exe < file.hiuh | head -50"`
Correct: `cmd /c ".\tokenizer.exe < file.hiuh" | Select-Object -First 50`

## Diagnosing parser output bugs: check the token stream first

When the parser produces wrong assembly, run:
```
hiuh-tokenizer.exe < source.hiuh
```
before the full pipeline. Wrong tokens (e.g. `pluss` instead of `PLUS`) point to a
tokenizer or compiler bug, not a parser logic bug. The token stream is the boundary
between the two halves.

## Global variable declarations in HIUH code

HIUH has an explicit `Deklarera` keyword for declaring global buffers (Text) and integers (Heltal) before use. This is required for self-hosting:

```hiuh
Deklarera tok som Text         . Declare a Text global (256 bytes in .bss)
Deklarera reg_next som Heltal  . Declare an integer global (8 bytes in .bss)
```

**Rules:**
- All `Deklarera` statements must appear **before** the first `Funktion` definition
- The Python compiler (`hiuh-native.py`) auto-tracks globals via `var_types` dict
- The self-hosted parser uses a runtime globals table (`gn0..gn7`, `gt0..gt7`) to track declared names and types
- When a global is passed as an argument to `Anropa`, the parser emits the correct load instruction:
  - Text global: `lea name(%rip), %rCX`
  - Heltal global: `mov name(%rip), %rCX`

This avoids the linker error "relocation truncated to fit: R_X86_64_32S" that would occur from incorrect 32-bit absolute addressing (`mov $name, %rCX`).
