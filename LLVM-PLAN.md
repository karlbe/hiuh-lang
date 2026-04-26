# HIUH Compiler Architecture med LLVM

## Mål

**EN kompilator** → **FLERA målplattformar**

```
HIUH-kod
    ↓
[Tokenisering] → [AST]
    ↓
[Typkontroll] (i hiuhpp)
    ↓
[LLVM IR] (.ll format)
    ↓
    ├─→ wasm backend ──→ .wasm
    │
    └─→ x86_64 backend ──→ ELF (Linux)
                         ──→ PE (Windows)
                         ──→ Mach-O (macOS)
```

## Varför LLVM?

| Egenskap | LLVM | Egen backend |
|----------|------|-------------|
| Mål-plattformar | wasm, x86, ARM, RISC-V, många fler | Bara en i taget |
| Optimering | Inbyggd i IR | Måste skriva själv |
| Underhåll | Gemensamt projekt | Eget arbete |
| Bindings | llvmlite (Python), Clang C API | Måste skriva C |

## Komponenter

### 1. Frontend (`hiuh-frontend.py`)

- Tokenizer (fungerar redan)
- Parser → AST
- Typkontroll (hiuhpp-specifikt)
- AST → LLVM IR

### 2. LLVM mellanrepresentation

Använd `llvmlite` (Python LLVM-binding) eller generera `.ll`-filer direkt.

```llvm
; Generated HIUH IR
@msg = internal constant [12 x i8] c"Hej vaerlden\00"

define i32 @_start() {
entry:
    call i32 @puts(i8* getelementptr([12 x i8], [12 x i8]* @msg, i32 0, i32 0))
    ret i32 0
}

declare i32 @puts(i8*)
```

### 3. Backend (målplattformar)

| Mål | LLVM target | Output |
|-----|-------------|--------|
| WebAssembly | `wasm32-unknown-unknown` | `.wasm` |
| Linux x86_64 | `x86_64-unknown-linux-gnu` | ELF executable |
| Windows x86_64 | `x86_64-pc-windows-gnu` | `.exe` |
| macOS ARM64 | `arm64-apple-darwin` | Mach-O |

### 4. Verktyg som behövs

```bash
# Installera llvmlite
pip install llvmlite

# Eller använd LLVM toolkit direkt
apt install llvm-17         # LLVM compiler (llc)
apt install clang-17         # C-kompilator (kan kompilera .ll → .s)
apt install lld-17           # Linker
```

## Implementation

### Steg 1: Installera beroenden

```bash
pip install llvmlite
# eller
apt install llvm-17 llvm-17-dev clang-17 lld-17
```

### Steg 2: Generera LLVM IR

```python
# hiuh-llvm.py
import llvmlite.ir as ir
import llvmlite.binding as llvm

llvm.initialize()
llvm.initialize_native_target()
llvm.initialize_native_asmprinter()

# Skapa module
module = ir.Module('hiuh')
module.triple = 'x86_64-unknown-linux-gnu'

# Definiera funktioner
func_type = ir.FunctionType(ir.IntType(32), [])
func = ir.Function(module, func_type, name='_start')

builder = ir.IRBuilder(func.append_basic_block())
# ... bygg IR ...
```

### Steg 3: Kompilera till mål

```python
# Kompilera till WebAssembly
target = llvm.Target.from_default_triple('wasm32-unknown-unknown')
target_machine = target.target_machine()
mod = llvm.parse_assembly(str(llvm_ir))
mod.triple = 'wasm32-unknown-unknown'
target_machine.set_feature('+simd128')  # Optional features
target_machine.emit_object(mod, 'output.o')

# För wasm, konvertera object → wasm med lld
subprocess.run(['lld', '-flavor', 'wasm', '-o', 'output.wasm', 'output.o'])
```

### Steg 4: Kompilera till x86_64

```python
target = llvm.Target.from_default_triple()
target_machine = target.target_target_machine()
mod = llvm.parse_assembly(str(llvm_ir))
target_machine.emit_object(mod, 'output.o')
subprocess.run(['ld', '-o', 'output', 'output.o'])
```

## Fördelar med LLVM-designen

1. **EN kodbas** – samma frontend, olika backends
2. **Optimerings-passes** – LLVM:s inbyggda optimering
3. **Debug info** – DWARF stöd direkt
4. **JIT-kompilering** – möjligt för interaktiv HIUH

## Alternativ: Använd `wat2wasm` + `lld`

Om vi inte vill använda llvmlite, kan vi:

1. Generera `.wat` (WAT text format)
2. Använda `wat2wasm` → `.wasm`
3. Använda `lld` för native:

```bash
# Konvertera WAT → WASM
wat2wasm input.wat -o output.wasm

# Eller: generera .ll → .s → obj → ELF
llc -march=x86_64 input.ll -o output.s
as -o output.o output.s
ld -o output output.o -lc
```

## Tidsplan

| Steg | Uppgift | Prioritet |
|------|---------|-----------|
| 1 | Installera LLVM/llvmlite | HÖG |
| 2 | Generera `.ll` istället för `.wat` | HÖG |
| 3 | Kompilera `.ll` → x86_64 ELF | HÖG |
| 4 | Kompilera `.ll` → WASM | MEDEL |
| 5 | Lägg till typkontroll (hiuhpp) | MEDEL |
| 6 | Optimering-passes | LÅG |
| 7 | Windows PE output | LÅG |

## Exempel: Fullständig pipeline

```bash
# Input: program.hiuh
# Output: native executable ELLER wasm

$ python3 hiuh.py program.hiuh --target wasm32
→ program.wasm

$ python3 hiuh.py program.hiuh --target x86_64
→ program (native ELF)

$ python3 hiuh.py program.hiuh --target arm64-darwin
→ program (macOS ARM64)
```

## Källkodstruktur (föreslagen)

```
hiuh/
├── hiuh.py              # WebAssembly kompilator (befintlig)
├── hiuh-llvm.py         # LLVM-baserad kompilator (NY)
├── hiuhpp/              # Hårt typad version (NY)
│   ├── type_checker.py  # Typkontroll
│   ├── ast.py           # AST definitioner
│   └── llvm_ir.py       # LLVM IR generator
└── native/              # Native kompilator
    └── hiuh-native.py   # Assembly-baserad (befintlig)
```

## Sammanfattning

Med LLVM kan vi:
- ✅ Använda **EN frontend** för ALLA målplattformar
- ✅ Få **gratis optimeringar**
- ✅ Stödja **WASM + x86_64 + ARM + mer**
- ✅ Få **debug info** (DWARF)
- ✅ **JIT-kompilering** för interaktiv körning

Vill du att jag börjar implementera LLVM-backend? 🧮
