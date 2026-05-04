# HIUH Self-Hosting Fixpoint — Summary & Next Steps

## What This Is About

The HIUH language is a self-hosting compiler. The goal: parser → parser2 → parser3 should produce identical assembly (fixpoint). Currently parser2.exe (self-compiled) crashes with STATUS_STACK_OVERFLOW on any input.

## Fixes Already Applied to `src/hiuh-parser.hiuh`

1. **Inkludera paths** (line 4-6): Changed to `src/hitta-var.hiuh`, `src/alloc-slot.hiuh`, `src/skriv-reg.hiuh` so the tokenizer's runtime `LäsFil` can find them from CWD.

2. **L1 emission order** (line ~1611): Added DECLARE check alongside FUNKTION check so DECLARE tokens don't trigger premature L1 emission. Before: DECLARE was NOT FUNKTION, so L1 was emitted too early (between included-file functions and parser's own functions). After: DECLARE is skipped just like FUNKTION, so L1 comes after ALL functions.

3. **Missing buffer declarations** (lines ~1622+): Added .data section with fmt_int, fmt_int_nonl, fmt_s, input_buf, _hiuh_incl_mode, tok_buf, tok_name_buf, ord_buf, vname0-5, label_buf, func_done_label_buf, func_over_label_buf, func_mode_buf, saved_reg_next_buf, for_reg_buf, has_comma_buf, block_buf. Added .bss entries for _hiuh_incl_buf (65536 bytes), _hiuh_incl_pos, _hiuh_incl_end, _hiuh_incl_fp.

**Result after these fixes:** parser2.exe links successfully (75177 bytes) but crashes with STATUS_STACK_OVERFLOW on ANY input (even empty stdin).

## Root Cause: READ Handler Doesn't Copy input_buf → Target Variable

The Python compiler handles `Läs till tok` as `READ_TO_VAR tok` which generates a `strcpy` from input_buf to the target buffer.

The self-hosted parser handles `Läs till tok` as three separate tokens:
1. READ → reads stdin into input_buf (strip newlines) — **but never copies to the variable**
2. "till" → no handler matches, silently ignored
3. "tok" → no handler matches, silently ignored

**The main loop** in parser2.exe (at label L1 in parser2.s) calls `hantera(tok_buf, reg_next)` but `tok_buf` is **never updated** from stdin reads. The read content stays in `input_buf` but hantera's comparisons use `tok_buf`. Since `tok_buf` is always empty, no token ever matches, and the program misbehaves.

## Proposed Fix (Not Yet Applied)

Add a handler for the "till" token in the `hantera` function. When hantera sees `till`:
1. Read next token (variable name) from stdin
2. Emit `strcpy` from `input_buf` to the target variable buffer

This makes `Läs till x` work correctly for ALL cases (main loop, function parameter reads, etc.).

**Where to add:** After the READ handler in `hantera` (around line 1262 in hiuh-parser.hiuh), before the KOPIERA_BUF handler.

**The code pattern to add** should:
1. Read the next token via `Läs`
2. Check if it equals "till" (Jämför)
3. If yes:
   a. `Läs` to get the variable name
   b. Save variable name to `tok_name_buf` (KopieraBuffer)
   c. Emit push r8-r11 + subq $32 wrapper
   d. Emit `strcpy` (lea tok_name_buf + input_buf → call strcpy) similar to KOPIERA_BUF handler
   e. Emit addq $32 + pop r8-r11 wrapper
4. If no "till": dispatch the token back (the token is next statement's first word)

**IMPORTANT CAVEAT:** The tokenizer emits words in varying cases. `Läs` becomes `READ` (uppercase, from emit_word). `till` needs to be checked to see if it's emitted as "till" or "TILL" or some other form. Check the tokenizer's `emit_word` function in `src/hiuh-tokenizer.hiuh` to confirm case conversion.

## Quick Workaround (Simpler)

Instead of modifying the READ handler, add `KopieraBuffer input_buf till tok` after each `Läs till tok` in the parser source. This explicitly copies input_buf → tok. The KOPIERA_BUF handler already generates correct strcpy.

Locations needing fix (~14 total):
- Main loop: lines ~1609 and ~1623 (2 occurrences)
- FUNKTION handler: lines ~1365, 1382, 1389, 1398, 1403, 1418, 1423, 1448 (8 occurrences)
- ANROPA echo handler: line ~1474 (1 occurrence)
- Tokenizer (separate fix, not critical for parser fixpoint): lines ~518, 560 (2 occurrences)
- Plus line ~457 in hantera (the ANROPA_RES handler)

## Build & Test Commands

```powershell
# Recompile tokenizer & parser (Python compiler)
python compiler/hiuh-native.py src/hiuh-tokenizer.hiuh hiuh-tokenizer.exe
python compiler/hiuh-native.py src/hiuh-parser.hiuh hiuh-parser.exe

# Generate parser2.s
cmd /c ".\hiuh-tokenizer.exe < src\hiuh-parser.hiuh | .\hiuh-parser.exe > parser2.s"

# Assemble & link
G:\msys64\mingw64\bin\as.exe -o parser2.o parser2.s
G:\msys64\mingw64\bin\ld.exe -o parser2-full.exe parser2.o -lmingw32 -lmsvcrt -lkernel32

# Test with simple input (should produce assembly, not crash)
cmd /c ".\hiuh-tokenizer.exe < test\test-func-main-order.hiuh | .\parser2-full.exe > test-out.s"

# Test with full parser source (fixpoint check)
cmd /c ".\hiuh-tokenizer.exe < src\hiuh-parser.hiuh > tokens.txt"
cmd /c ".\parser2-full.exe < tokens.txt > parser3.s"

# Compare parser2.s vs parser3.s
fc parser2.s parser3.s

# Debug crash with GDB
gdb --batch -ex "run < tokens.txt" -ex "backtrace" -ex "info registers" .\parser2-full.exe
```

## Key Files

| File | Purpose |
|---|---|
| `src/hiuh-parser.hiuh` | Parser source (1651→1681 lines after edits) |
| `src/hiuh-tokenizer.hiuh` | Tokenizer source |
| `src/hitta-var.hiuh` | Variable lookup helper |
| `src/alloc-slot.hiuh` | Slot allocation helper |
| `src/skriv-reg.hiuh` | Register name emitter helper |
| `compiler/hiuh-native.py` | Python compiler (source of truth) |
| `build-pipeline.ps1` | Build script |
| `parser2.s` | Current pipeline output (~259KB) |
| `parser2-full.exe` | Self-compiled parser (~75KB) |
| `tokens.txt` | Tokenized parser source (~40KB, 5951 tokens) |

## What parser2.exe SHOULD do when working

1. main prologue → jmp L1 → skips functions → enters main body at L1
2. L1 code runs through token dispatch (GE, ANROPA, etc.) — all comparisons fail with empty tok_buf
3. Falls through to initialization: lagra_label_nr(0), block_buf = 0
4. Emits assembly header via puts (".text", "main:", etc.)
5. Enters main loop:
   a. READ token into input_buf
   b. COPY input_buf → tok_buf (BUG: this step is missing!)
   c. Check tok_buf for "FUNKTION"/"DECLARE", emit L1 if needed
   d. Call hantera(tok_buf, reg_next)
   e. READ next token → loop
6. After loop: emits epilogue + declarations via puts
7. Returns from main
