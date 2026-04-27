#!/usr/bin/env python3
"""
HIUH Compiler - Lists support
Sätt abc till lista
Sätt abc till lista av 1, 2, 3
Lägg till 2 till abc
"""

import sys

def tokenize(src):
    tokens = []
    for lineno, line in enumerate(src.split('\n'), 1):
        stripped = line.lstrip()
        if not stripped:
            continue
        words = stripped.split()
        first = words[0]
        
        if first == 'Skriv':
            tokens.append(('SKRIV', ' '.join(words[1:]), lineno))
        elif first == 'Sätt' and len(words) >= 4:
            var = words[1]
            rest = ' '.join(words[3:])
            if 'lista av' in rest:
                # Extract list items
                items_start = rest.index('lista av') + len('lista av')
                items_str = rest[items_start:].strip()
                items = [x.strip() for x in items_str.split(',')]
                tokens.append(('LIST_INIT', f'{var}:{items_str}', lineno))
            elif rest == 'lista':
                tokens.append(('LIST_NEW', var, lineno))
            else:
                tokens.append(('SATT', f'{var}:{rest}', lineno))
        elif first == 'Lägg' and len(words) >= 4:
            if words[1] == 'till' and 'till' in words:
                # "Lägg till X till Y" -> append X to Y
                item = words[2] if len(words) > 2 else ''
                target = words[4] if len(words) > 4 else ''
                tokens.append(('LIST_APPEND', f'{item}:{target}', lineno))
        elif first == 'För' and len(words) >= 5:
            var = words[1]
            try:
                fi = words.index('från')
                ti = words.index('till')
                start = ' '.join(words[fi+1:ti])
                end = ' '.join(words[ti+1:])
            except:
                start, end = '0', '10'
            tokens.append(('FOR', f'{var}:{start}:{end}', lineno))
        elif first == 'Hejdå':
            tokens.append(('HEJDA', '', lineno))
        elif first == 'JagMåsteGåNu':
            code = words[1] if len(words) > 1 and words[1].isdigit() else '0'
            tokens.append(('EXIT', code, lineno))
        else:
            tokens.append(('EXPR', stripped, lineno))
        
        tokens.append(('NEWLINE', '', lineno))
    
    return tokens

def parse(tokens):
    stmts = []
    i = 0
    while i < len(tokens):
        typ, val, lineno = tokens[i]
        
        if typ == 'SKRIV':
            stmts.append(('SKRIV', val))
            i += 1
        elif typ == 'LIST_NEW':
            stmts.append(('LIST_NEW', val))  # val = list name
            i += 1
        elif typ == 'LIST_INIT':
            parts = val.split(':')
            name = parts[0]
            items = parts[1] if len(parts) > 1 else ''
            stmts.append(('LIST_INIT', name, items))
            i += 1
        elif typ == 'LIST_APPEND':
            parts = val.split(':')
            item = parts[0]
            target = parts[1] if len(parts) > 1 else ''
            stmts.append(('LIST_APPEND', item, target))
            i += 1
        elif typ == 'FOR':
            parts = val.split(':')
            var, start, end = parts[0], parts[1] if len(parts) > 1 else '0', parts[2] if len(parts) > 2 else '10'
            body, i = parse_block(tokens, i)
            stmts.append(('FOR', var, start, end, body))
        elif typ == 'EXIT':
            stmts.append(('EXIT', val))
            i += 1
        elif typ == 'HEJDA':
            break
        else:
            i += 1
    
    return stmts

def parse_block(tokens, start_i):
    body = []
    i = start_i
    while i < len(tokens):
        typ = tokens[i][0]
        if typ == 'HEJDA':
            i += 1
            break
        if typ == 'SKRIV':
            body.append(('SKRIV', tokens[i][1]))
            i += 1
        elif typ == 'LIST_NEW':
            body.append(('LIST_NEW', tokens[i][1]))
            i += 1
        elif typ == 'LIST_INIT':
            parts = tokens[i][1].split(':')
            body.append(('LIST_INIT', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'LIST_APPEND':
            parts = tokens[i][1].split(':')
            body.append(('LIST_APPEND', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        else:
            i += 1
    return body, i

def generate_wat(statements):
    strings = []
    def add_string(s):
        if s not in strings:
            strings.append(s)
        return strings.index(s)
    
    wat = """(module
  (memory (export "memory") 1)

  (import "wasi_snapshot_preview1" "fd_write"
    (func $fd_write (param i32 i32 i32 i32) (result i32)))
  (import "wasi_snapshot_preview1" "proc_exit"
    (func $proc_exit (param i32)))

  (global $heap_ptr (mut i32) (i32.const 32768))

  (func (export "_start")
"""
    
    for stmt in statements:
        if stmt[0] == 'SKRIV':
            idx = add_string(stmt[1])
            off = idx * 64
            wat += f'    (call $fd_write (i32.const 1) (i32.const {off}) (i32.const {len(stmt[1])}) (i32.const 0))\n'
        elif stmt[0] == 'LIST_INIT':
            # Initialize list with values
            name = stmt[1]
            items_str = stmt[2]
            if items_str:
                items = [x.strip() for x in items_str.split(',')]
                # Store list metadata: [pointer, length]
                # Allocate in heap
                wat += f'    ;; {name} = [{items_str}]\n'
                wat += f'    (global.set $heap_ptr (i32.add (global.get $heap_ptr) (i32.const {8 * (len(items) + 1)})))\n'
        elif stmt[0] == 'EXIT':
            code = stmt[1] if stmt[1].isdigit() else '0'
            wat += f'    (call $proc_exit (i32.const {code}))\n'
    
    wat += """  )
"""
    
    # Data section
    data = '(data (i32.const 0) "'
    for s in strings:
        escaped = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\0a')
        data += escaped + '\\00'
    data += '")\n'
    wat += '  ' + data + ')\n'
    
    return wat

def generate_asm(statements):
    lines = []
    lines.append(".text")
    lines.append(".globl _start")
    lines.append("_start:")
    
    for stmt in statements:
        if stmt[0] == 'SKRIV':
            msg = stmt[1] + '\n'
            lines.append(f"    .data")
            lines.append(f"msg_{len([m for m in lines if 'msg_' in m])}: .ascii \"{msg.replace(chr(10), '\\n')}\"")
            lines.append(f"    .text")
            lines.append(f"    mov $1, %rax")
            lines.append(f"    mov $1, %rdi")
            lines.append(f"    lea msg_0(%rip), %rsi")
            lines.append(f"    mov ${len(msg)}, %rdx")
            lines.append(f"    syscall")
        elif stmt[0] == 'LIST_INIT':
            name, items_str = stmt[1], stmt[2]
            if items_str:
                items = [x.strip() for x in items_str.split(',')]
                lines.append(f"    ;; {name} = [{items_str}]")
                lines.append(f"    .quad {len(items)}        # {name} length")
                for item in items:
                    lines.append(f"    .quad {item}        # {name} item")
        elif stmt[0] == 'EXIT':
            lines.append(f"    mov ${stmt[1]}, %rdi")
            lines.append(f"    mov $60, %rax")
            lines.append(f"    syscall")
    
    # exit(0) if no explicit exit
    lines.append("    mov $60, %rax")
    lines.append("    xor %rdi, %rdi")
    lines.append("    syscall")
    
    return '\n'.join(lines)

def create_html(wat):
    escaped = wat.replace('\\', '\\\\').replace('`', '\\`')
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>HIUH Lists</title></head>
<body><h1>Lists Demo</h1>
<pre id="code>{escaped}</pre>
<button onclick="run()">Kör</button>
<pre id="out">Tryck...</pre>
<script src="https://cdn.jsdelivr.net/npm/wabt@1.0.32/index.js"></script>
<script>
let wabt=null, mem=null;
async function init(){{if(!wabt)wabt=await WabtModule();return wabt;}}
async function run(){{
const out=document.getElementById('out');
out.textContent='Kör...';
try{{
const mod=await init().then(w=>w.parseWat('h',document.getElementById('code').textContent));
const bin=mod.toBinary({{}});
const {{instance}}=await WebAssembly.instantiate(bin.buffer,{{
wasi_snapshot_preview_preview1:{{
fd_write:(fd,p,len)=>{{if(fd===1)out.textContent+=new TextDecoder().decode(new Uint8Array(mem.buffer).slice(p,p+len));return 0;}},
proc_exit:(c)=>{{out.textContent+='\\n[Exit '+c+']';throw Error('x');}}
}}}});
mem=instance.exports.memory;
if(instance.exports._start)instance.exports._start();
out.textContent+='\\nKlart!';
}}catch(e){{if(e.message!=='x')out.textContent+='\\nFel: '+e.message;}}
}}
</script></body></html>'''

def compile(src):
    tokens = tokenize(src)
    stmts = parse(tokens)
    wat = generate_wat(stmts)
    return create_html(wat)

def compile_native(src):
    tokens = tokenize(src)
    stmts = parse(tokens)
    return generate_asm(stmts)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 hiuh-lists.py <input.hiuh> [output.html]")
        return
    src = open(sys.argv[1]).read()
    if '--asm' in sys.argv:
        print(compile_native(src))
    else:
        html = compile(src)
        out = sys.argv[2] if len(sys.argv) > 2 else 'lists.html'
        open(out, 'w').write(html)
        print(f"Kompilerade till {out}")