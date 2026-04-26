#!/usr/bin/env python3
"""
HIUH Compiler - Full feature set for self-hosting
No special characters: no [], no +, no quotes!
"""

import sys

# Token types
TOK_SKRIV = 'SKRIV'
TOK_SKRIV_VAR = 'SKRIV_VAR'
TOK_SATT = 'SATT'
TOK_LIST_NEW = 'LIST_NEW'
TOK_LIST_INIT = 'LIST_INIT'
TOK_LIST_APPEND = 'LIST_APPEND'
TOK_OM = 'OM'
TOK_ANNARS = 'ANNARS'
TOK_HEJDA = 'HEJDA'
TOK_FOR = 'FOR'
TOK_EXIT = 'EXIT'
TOK_FILE_OPEN = 'FILE_OPEN'
TOK_FILE_READ = 'FILE_READ'
TOK_FILE_WRITE = 'FILE_WRITE'
TOK_ELEMENT_UR = 'ELEMENT_UR'
TOK_TECKEN_UR = 'TECKEN_UR'
TOK_SAMMANFOGAT = 'SAMMANFOGAT'
TOK_ANTAL = 'ANTAL'
TOK_NEWLINE = 'NEWLINE'

def tokenize(src):
    tokens = []
    for lineno, line in enumerate(src.split('\n'), 1):
        stripped = line.lstrip()
        if not stripped:
            tokens.append((TOK_NEWLINE, '', lineno))
            continue
        words = stripped.split()
        first = words[0]
        
        # SKRIV
        if first == 'Skriv':
            rest = ' '.join(words[1:])
            if rest.startswith('värdet av '):
                var = rest[len('värdet av '):]
                tokens.append((TOK_SKRIV_VAR, var.strip(), lineno))
            else:
                tokens.append((TOK_SKRIV, rest, lineno))
        
        # SÄTT
        elif first == 'Sätt' and len(words) >= 4:
            var = words[1]
            rest = ' '.join(words[3:])
            
            if rest == 'lista':
                tokens.append((TOK_LIST_NEW, var, lineno))
            elif 'lista av' in rest:
                items_start = rest.index('lista av') + len('lista av')
                items_str = rest[items_start:].strip()
                tokens.append((TOK_LIST_INIT, f'{var}:{items_str}', lineno))
            elif rest.startswith('till '):
                val = rest[len('till '):]
                tokens.append((TOK_SATT, f'{var}:{val}', lineno))
            else:
                tokens.append((TOK_SATT, f'{var}:{rest}', lineno))
        
        # LÄGG TILL ... TILL
        elif first == 'Lägg' and len(words) >= 5:
            if words[1] == 'till':
                item = words[2]
                target = words[4]
                tokens.append((TOK_LIST_APPEND, f'{item}:{target}', lineno))
        
        # OM
        elif first == 'Om':
            cond = ' '.join(words[1:])
            tokens.append((TOK_OM, cond, lineno))
        
        # ANNARS
        elif first == 'Annars':
            tokens.append((TOK_ANNARS, '', lineno))
        
        # HEJDÅ
        elif first == 'Hejdå':
            tokens.append((TOK_HEJDA, '', lineno))
        
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
            tokens.append((TOK_FOR, f'{var}:{start}:{end}', lineno))
        
        # JAG MÅSTE GÅ NU
        elif first == 'JagMåsteGåNu':
            code = words[1] if len(words) > 1 and words[1].isdigit() else '0'
            tokens.append((TOK_EXIT, code, lineno))
        
        # ÖPPNA
        elif first == 'Öppna':
            rest = ' '.join(words[1:])
            tokens.append((TOK_FILE_OPEN, rest, lineno))
        
        # LÄS
        elif first == 'Läs':
            if len(words) > 1:
                tokens.append((TOK_FILE_READ, ' '.join(words[1:]), lineno))
        
        # SKRIV TILL FIL
        elif first == 'SkrivTillFil':
            rest = ' '.join(words[1:])
            tokens.append((TOK_FILE_WRITE, rest, lineno))
        
        # ELEMENT ... UR (list index)
        elif 'element' in words and 'ur' in words:
            try:
                ei = words.index('element')
                ui = words.index('ur')
                idx = ' '.join(words[ei+1:ui])
                target = ' '.join(words[ui+1:])
                tokens.append((TOK_ELEMENT_UR, f'{idx}:{target}', lineno))
            except:
                pass
        
        # TECKEN ... UR (string index)
        elif 'tecken' in words and 'ur' in words:
            try:
                ti = words.index('tecken')
                ui = words.index('ur')
                idx = ' '.join(words[ti+1:ui])
                target = ' '.join(words[ui+1:])
                tokens.append((TOK_TECKEN_UR, f'{idx}:{target}', lineno))
            except:
                pass
        
        # SAMMANFOGAT MED
        elif 'sammanfogat' in words and 'med' in words:
            try:
                si = words.index('sammanfogat')
                mi = words.index('med')
                left = ' '.join(words[:si])
                right = ' '.join(words[mi+1:])
                tokens.append((TOK_SAMMANFOGAT, f'{left}:{right}', lineno))
            except:
                pass
        
        # ANTAL ELEMENT I
        elif first == 'Antal' and len(words) >= 4 and words[2] == 'element' and words[3] == 'i':
            target = ' '.join(words[4:])
            tokens.append((TOK_ANTAL, target, lineno))
        
        else:
            tokens.append(('EXPR', stripped, lineno))
        
        tokens.append((TOK_NEWLINE, '', lineno))
    
    return tokens

def parse(tokens):
    stmts = []
    i = 0
    while i < len(tokens):
        typ, val, lineno = tokens[i]
        
        if typ == TOK_SKRIV:
            stmts.append((TOK_SKRIV, val))
            i += 1
        elif typ == TOK_SKRIV_VAR:
            stmts.append((TOK_SKRIV_VAR, val))
            i += 1
        elif typ == TOK_SATT:
            parts = val.split(':', 1)
            stmts.append((TOK_SATT, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == TOK_LIST_NEW:
            stmts.append((TOK_LIST_NEW, val))
            i += 1
        elif typ == TOK_LIST_INIT:
            parts = val.split(':')
            stmts.append((TOK_LIST_INIT, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == TOK_LIST_APPEND:
            parts = val.split(':')
            stmts.append((TOK_LIST_APPEND, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == TOK_ELEMENT_UR:
            parts = val.split(':')
            idx = parts[0]
            target = parts[1] if len(parts) > 1 else ''
            stmts.append((TOK_ELEMENT_UR, idx, target))
            i += 1
        elif typ == TOK_TECKEN_UR:
            parts = val.split(':')
            idx = parts[0]
            target = parts[1] if len(parts) > 1 else ''
            stmts.append((TOK_TECKEN_UR, idx, target))
            i += 1
        elif typ == TOK_SAMMANFOGAT:
            parts = val.split(':')
            left = parts[0]
            right = parts[1] if len(parts) > 1 else ''
            stmts.append((TOK_SAMMANFOGAT, left, right))
            i += 1
        elif typ == TOK_ANTAL:
            stmts.append((TOK_ANTAL, val))
            i += 1
        elif typ == TOK_OM:
            body, else_b, i = parse_if(tokens, i)
            stmts.append((TOK_OM, body, else_b))
        elif typ == TOK_FOR:
            parts = val.split(':')
            var, start, end = parts[0], parts[1] if len(parts) > 1 else '0', parts[2] if len(parts) > 2 else '10'
            body, i = parse_block(tokens, i)
            stmts.append((TOK_FOR, var, start, end, body))
        elif typ == TOK_EXIT:
            stmts.append((TOK_EXIT, val))
            i += 1
        elif typ == TOK_FILE_OPEN:
            stmts.append((TOK_FILE_OPEN, val))
            i += 1
        elif typ == TOK_FILE_READ:
            stmts.append((TOK_FILE_READ, val))
            i += 1
        elif typ == TOK_FILE_WRITE:
            stmts.append((TOK_FILE_WRITE, val))
            i += 1
        elif typ == TOK_HEJDA:
            break
        else:
            i += 1
    
    return stmts

def parse_block(tokens, start_i):
    body = []
    i = start_i
    while i < len(tokens):
        typ = tokens[i][0]
        if typ == TOK_HEJDA:
            i += 1
            break
        if typ == TOK_SKRIV:
            body.append((TOK_SKRIV, tokens[i][1]))
            i += 1
        elif typ == TOK_SKRIV_VAR:
            body.append((TOK_SKRIV_VAR, tokens[i][1]))
            i += 1
        elif typ == TOK_SATT:
            parts = tokens[i][1].split(':', 1)
            body.append((TOK_SATT, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == TOK_LIST_NEW:
            body.append((TOK_LIST_NEW, tokens[i][1]))
            i += 1
        elif typ == TOK_LIST_APPEND:
            parts = tokens[i][1].split(':')
            body.append((TOK_LIST_APPEND, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == TOK_ELEMENT_UR:
            parts = tokens[i][1].split(':')
            body.append((TOK_ELEMENT_UR, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == TOK_SAMMANFOGAT:
            parts = tokens[i][1].split(':')
            body.append((TOK_SAMMANFOGAT, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == TOK_ANTAL:
            body.append((TOK_ANTAL, tokens[i][1]))
            i += 1
        elif typ == TOK_OM:
            then_b, else_b, i = parse_if(tokens, i)
            body.append((TOK_OM, then_b, else_b))
        elif typ == TOK_FOR:
            parts = tokens[i][1].split(':')
            var = parts[0]
            start = parts[1] if len(parts) > 1 else '0'
            end = parts[2] if len(parts) > 2 else '10'
            loop_body, i = parse_block(tokens, i)
            body.append((TOK_FOR, var, start, end, loop_body))
        elif typ == TOK_EXIT:
            body.append((TOK_EXIT, tokens[i][1]))
            i += 1
        elif typ == TOK_FILE_WRITE:
            body.append((TOK_FILE_WRITE, tokens[i][1]))
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
        if typ == TOK_ANNARS:
            i += 1
            continue
        if typ == TOK_OM:
            nested_then, nested_else, i = parse_if(tokens, i - 1)
            then_body.extend(nested_then)
            if nested_else:
                else_body.extend(nested_else)
            continue
        if typ == TOK_HEJDA:
            i += 1
            break
        if typ == TOK_SKRIV:
            then_body.append((TOK_SKRIV, val))
            i += 1
        elif typ == TOK_SKRIV_VAR:
            then_body.append((TOK_SKRIV_VAR, val))
            i += 1
        elif typ == TOK_SATT:
            parts = val.split(':', 1)
            then_body.append((TOK_SATT, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == TOK_EXIT:
            then_body.append((TOK_EXIT, val))
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
        if stmt[0] == TOK_SKRIV:
            idx = add_string(stmt[1])
            off = idx * 64
            wat += f'    (call $fd_write (i32.const 1) (i32.const {off}) (i32.const {len(stmt[1])}) (i32.const 0))\n'
        elif stmt[0] == TOK_SKRIV_VAR:
            var = stmt[1]
            idx = add_string(f'{var}\\n')
            off = idx * 64
            wat += f'    (call $fd_write (i32.const 1) (i32.const {off}) (i32.const {len(var)+1}) (i32.const 0))\n'
        elif stmt[0] == TOK_EXIT:
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