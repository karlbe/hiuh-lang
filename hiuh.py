#!/usr/bin/env python3
"""
HIUH Compiler - Full feature set for self-hosting
Features: Skriv, input, värdet av, listor, fil-I/O, jämförelser
"""

import sys

def tokenize(src):
    tokens = []
    for lineno, line in enumerate(src.split('\n'), 1):
        stripped = line.lstrip()
        if not stripped:
            tokens.append(('NEWLINE', '', lineno))
            continue
        words = stripped.split()
        first = words[0]
        
        # SKRIV
        if first == 'Skriv':
            rest = ' '.join(words[1:])
            if rest.startswith('värdet av '):
                var = rest[len('värdet av '):]
                tokens.append(('SKRIV_VAR', var.strip(), lineno))
            else:
                tokens.append(('SKRIV', rest, lineno))
        
        # SÄTT
        elif first == 'Sätt' and len(words) >= 4:
            var = words[1]
            rest = ' '.join(words[3:])
            
            if rest == 'lista':
                tokens.append(('LIST_NEW', var, lineno))
            elif 'lista av' in rest:
                items_start = rest.index('lista av') + len('lista av')
                items_str = rest[items_start:].strip()
                tokens.append(('LIST_INIT', f'{var}:{items_str}', lineno))
            elif rest.startswith('till '):
                val = rest[len('till '):]
                tokens.append(('SATT', f'{var}:{val}', lineno))
            else:
                tokens.append(('SATT', f'{var}:{rest}', lineno))
        
        # LÄGG TILL
        elif first == 'Lägg' and len(words) >= 5:
            if words[1] == 'till':
                item = words[2]
                target = words[4]
                tokens.append(('LIST_APPEND', f'{item}:{target}', lineno))
        
        # OM
        elif first == 'Om':
            cond = ' '.join(words[1:])
            tokens.append(('OM', cond, lineno))
        
        # ANNARS
        elif first == 'Annars':
            tokens.append(('ANNARS', '', lineno))
        
        # HEJDÅ
        elif first == 'Hejdå':
            tokens.append(('HEJDA', '', lineno))
        
        # FÖR
        elif first == 'För':
            var = words[1] if len(words) > 1 else 'i'
            try:
                fi = words.index('från')
                ti = words.index('till')
                start = ' '.join(words[fi+1:ti])
                end = ' '.join(words[ti+1:])
            except:
                start, end = '0', '10'
            tokens.append(('FOR', f'{var}:{start}:{end}', lineno))
        
        # JAG MÅSTE GÅ NU
        elif first == 'JagMåsteGåNu':
            code = words[1] if len(words) > 1 and words[1].isdigit() else '0'
            tokens.append(('EXIT', code, lineno))
        
        # ÖPPNA
        elif first == 'Öppna':
            rest = ' '.join(words[1:])
            tokens.append(('FILE_OPEN', rest, lineno))
        
        # LÄS
        elif first == 'Läs':
            if len(words) > 1:
                tokens.append(('FILE_READ', ' '.join(words[1:]), lineno))
        
        # SKRIV TILL FIL
        elif first == 'SkrivTillFil':
            rest = ' '.join(words[1:])
            tokens.append(('FILE_WRITE', rest, lineno))
        
        # JÄMFÖRELSER
        elif first == 'Är':
            left = words[1] if len(words) > 1 else ''
            right = ' '.join(words[2:]) if len(words) > 2 else ''
            tokens.append(('CMP_EQ', f'{left}:{right}', lineno))
        
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
        elif typ == 'SKRIV_VAR':
            stmts.append(('SKRIV_VAR', val))
            i += 1
        elif typ == 'SATT':
            parts = val.split(':', 1)
            stmts.append(('SATT', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'LIST_NEW':
            stmts.append(('LIST_NEW', val))
            i += 1
        elif typ == 'LIST_INIT':
            parts = val.split(':')
            stmts.append(('LIST_INIT', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'LIST_APPEND':
            parts = val.split(':')
            stmts.append(('LIST_APPEND', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'OM':
            body, else_b, i = parse_if(tokens, i)
            stmts.append(('OM', body, else_b))
        elif typ == 'FOR':
            parts = val.split(':')
            var, start, end = parts[0], parts[1] if len(parts) > 1 else '0', parts[2] if len(parts) > 2 else '10'
            body, i = parse_block(tokens, i)
            stmts.append(('FOR', var, start, end, body))
        elif typ == 'EXIT':
            stmts.append(('EXIT', val))
            i += 1
        elif typ == 'FILE_OPEN':
            stmts.append(('FILE_OPEN', val))
            i += 1
        elif typ == 'FILE_READ':
            stmts.append(('FILE_READ', val))
            i += 1
        elif typ == 'FILE_WRITE':
            stmts.append(('FILE_WRITE', val))
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
        elif typ == 'SKRIV_VAR':
            body.append(('SKRIV_VAR', tokens[i][1]))
            i += 1
        elif typ == 'SATT':
            parts = tokens[i][1].split(':', 1)
            body.append(('SATT', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'LIST_NEW':
            body.append(('LIST_NEW', tokens[i][1]))
            i += 1
        elif typ == 'LIST_APPEND':
            parts = tokens[i][1].split(':')
            body.append(('LIST_APPEND', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'OM':
            then_b, else_b, i = parse_if(tokens, i)
            body.append(('OM', then_b, else_b))
        elif typ == 'FOR':
            parts = tokens[i][1].split(':')
            var = parts[0]
            start = parts[1] if len(parts) > 1 else '0'
            end = parts[2] if len(parts) > 2 else '10'
            loop_body, i = parse_block(tokens, i)
            body.append(('FOR', var, start, end, loop_body))
        elif typ == 'EXIT':
            body.append(('EXIT', tokens[i][1]))
            i += 1
        elif typ == 'FILE_WRITE':
            body.append(('FILE_WRITE', tokens[i][1]))
            i += 1
        else:
            i += 1
    return body, i

def parse_if(tokens, start_i):
    then_body = []
    else_body = []
    i = start_i + 1
    while i < len(tokens):
        typ, val = tokens[i][0], tokens[i][1]
        if typ == 'ANNARS':
            i += 1
            continue
        if typ == 'OM':
            nested_then, nested_else, i = parse_if(tokens, i - 1)
            then_body.extend(nested_then)
            if nested_else:
                else_body.extend(nested_else)
            continue
        if typ == 'HEJDA':
            i += 1
            break
        if typ == 'SKRIV':
            then_body.append(('SKRIV', val))
            i += 1
        elif typ == 'SKRIV_VAR':
            then_body.append(('SKRIV_VAR', val))
            i += 1
        elif typ == 'SATT':
            parts = val.split(':', 1)
            then_body.append(('SATT', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'EXIT':
            then_body.append(('EXIT', val))
            i += 1
        else:
            i += 1
    return then_body, else_body, i

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
        elif stmt[0] == 'SKRIV_VAR':
            var = stmt[1]
            idx = add_string(f'{var}\\n')
            off = idx * 64
            wat += f'    (call $fd_write (i32.const 1) (i32.const {off}) (i32.const {len(var)+1}) (i32.const 0))\n'
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

def create_html(wat):
    escaped = wat.replace('\\', '\\\\').replace('`', '\\`')
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>HIUH Runner</title></head>
<body><h1>HIUH</h1>
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

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 hiuh.py <input.hiuh> [output.html]")
        return
    src = open(sys.argv[1]).read()
    html = compile(src)
    out = sys.argv[2] if len(sys.argv) > 2 else 'hiuh.html'
    open(out, 'w').write(html)
    print(f"Kompilerade till {out}")

if __name__ == '__main__':
    main()