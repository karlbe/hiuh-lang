#!/usr/bin/env python3
"""
HIUH Compiler - Full sentences, no quotes, indentation-based
Mobile-friendly Swedish programming language!
"""

import sys
from typing import *

class PrintStmt:
    def __init__(self, text):
        self.text = text

class Assign:
    def __init__(self, name, value):
        self.name = name
        self.value = value

class IfStmt:
    def __init__(self, cond, then_body, else_body):
        self.cond = cond
        self.then_body = then_body
        self.else_body = else_body

class ForStmt:
    def __init__(self, var, start, end, body):
        self.var = var
        self.start = start
        self.end = end
        self.body = body

def tokenize(src):
    tokens = []
    lines = src.split('\n')
    
    for lineno, line in enumerate(lines, 1):
        stripped = line.lstrip()
        
        if not stripped:
            tokens.append(('NEWLINE', '', lineno))
            continue
        
        words = stripped.split()
        first = words[0]
        
        if first == 'Skriv':
            tokens.append(('SKRIV', ' '.join(words[1:]), lineno))
        elif first == 'Sätt' and len(words) >= 4:
            var = words[1]
            if 'till' in words:
                idx = words.index('till')
                val = ' '.join(words[idx+1:])
            else:
                val = ' '.join(words[3:])
            tokens.append(('SATT', f'{var}:{val}', lineno))
        elif first == 'Om':
            tokens.append(('OM', ' '.join(words[1:]), lineno))
        elif first == 'Annars':
            tokens.append(('ANNARS', ' '.join(words[1:]), lineno))
        elif first == 'Hejdå':
            tokens.append(('HEJDA', '', lineno))
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
        elif ':=' in stripped:
            var, val = stripped.split(':=')
            tokens.append(('SATT', f'{var.strip()}:{val.strip()}', lineno))
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
            stmts.append(PrintStmt(val))
            i += 1
        elif typ == 'SATT':
            parts = val.split(':')
            stmts.append(Assign(parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'OM':
            then_b, else_b, i = parse_if(tokens, i)
            stmts.append(IfStmt(val, then_b, else_b))
        elif typ == 'FOR':
            parts = val.split(':')
            var, start, end = parts[0], parts[1] if len(parts) > 1 else '0', parts[2] if len(parts) > 2 else '10'
            body, i = parse_block(tokens, i)
            stmts.append(ForStmt(var, start, end, body))
        elif typ == 'HEJDA':
            break
        else:
            i += 1
    
    return stmts

def parse_block(tokens, start_i):
    """Parse until HEJDA"""
    body = []
    i = start_i
    
    while i < len(tokens):
        typ, val = tokens[i][0], tokens[i][1]
        
        if typ == 'HEJDA':
            i += 1
            break
        elif typ == 'SKRIV':
            body.append(PrintStmt(val))
            i += 1
        elif typ == 'SATT':
            parts = val.split(':')
            body.append(Assign(parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'FOR':
            parts = val.split(':')
            var = parts[0]
            start = parts[1] if len(parts) > 1 else '0'
            end = parts[2] if len(parts) > 2 else '10'
            loop_body, i = parse_block(tokens, i)
            body.append(ForStmt(var, start, end, loop_body))
        else:
            i += 1
    
    return body, i

def parse_if(tokens, start_i):
    """Parse if/else block - iterative"""
    then_body = []
    else_body = []
    i = start_i + 1  # skip OM
    
    while i < len(tokens):
        typ, val = tokens[i][0], tokens[i][1]
        
        if typ == 'ANNARS':
            i += 1
            # Check for "Annars om X"
            if i < len(tokens) and tokens[i][0] == 'OM':
                # This is "else if" - parse inner if into then_body only
                inner_then, inner_else, i = parse_if(tokens, i - 1)
                # In "else if", the "else" part becomes current else_body
                if inner_else:
                    # Merge inner else into current else
                    else_body.extend(inner_else)
                else:
                    else_body.extend(inner_then)
            continue
        
        if typ == 'OM':
            # New if starts - this would be after "else", need HEJDA first
            break
        
        if typ == 'HEJDA':
            i += 1
            break
        
        if typ == 'SKRIV':
            then_body.append(PrintStmt(val))
            i += 1
        elif typ == 'SATT':
            parts = val.split(':')
            then_body.append(Assign(parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'FOR':
            parts = val.split(':')
            var = parts[0]
            start = parts[1] if len(parts) > 1 else '0'
            end = parts[2] if len(parts) > 2 else '10'
            loop_body, i = parse_block(tokens, i)
            then_body.append(ForStmt(var, start, end, loop_body))
        else:
            i += 1
    
    return then_body, else_body, i

def compile_to_wasm(statements):
    strings = []
    
    def add_string(s):
        if s not in strings:
            strings.append(s)
        return strings.index(s)
    
    wat = """(module
  (memory (export "memory") 1)

  (import "wasi_snapshot_preview1" "fd_write"
    (func $fd_write (param i32 i32 i32 i32) (result i32)))

  (func $print (param $p i32) (param $l i32)
    (call $fd_write (i32.const 1) (local.get $p) (local.get $l) (i32.const 0))
    (drop)
  )

  (func (export "_start")
"""
    
    for stmt in statements:
        if isinstance(stmt, PrintStmt):
            if stmt.text:
                idx = add_string(stmt.text)
                offset = idx * 64
                wat += f'    (call $print (i32.const {offset}) (i32.const {len(stmt.text)}))\n'
    
    wat += """  )

  (func (export "read") (param $i i32) (result i32)
    (i32.load8_u (local.get $i))
  )

  (func (export "write") (param $i i32) (param $v i32)
    (i32.store8 (local.get $i) (local.get $v))
  )
"""
    
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
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HIUH Runner</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Courier New', monospace; background: #1a1a2e; color: #eee; padding: 15px; min-height: 100vh; }}
        h1 {{ color: #e94560; margin-bottom: 15px; font-size: 1.5em; }}
        .controls {{ margin-bottom: 15px; }}
        .btn {{ background: #e94560; color: white; border: none; padding: 10px 20px; margin-right: 10px; cursor: pointer; border-radius: 5px; font-size: 16px; }}
        .btn:hover {{ background: #ff6b6b; }}
        #output {{ background: #16213e; color: #0f0; padding: 15px; min-height: 120px; white-space: pre-wrap; border-radius: 8px; border: 2px solid #e94560; font-size: 14px; }}
        #code {{ display: none; background: #16213e; color: #4ecca3; padding: 15px; font-size: 12px; overflow-x: auto; white-space: pre-wrap; }}
        .info {{ color: #888; margin-top: 15px; font-size: 14px; }}
    </style>
</head>
<body>
    <h1>HIUH Runner</h1>
    <div class="controls">
        <button class="btn" onclick="run()">Kör</button>
        <button class="btn" onclick="toggle()">Kod</button>
        <button class="btn" onclick="clear()">Rensa</button>
    </div>
    <pre id="output">Tryck "Kör" för att köra...\n</pre>
    <pre id="code">{escaped}</pre>
    <p class="info">Skicka HIUH-kod till @Klåd för kompilering!</p>

    <script src="https://cdn.jsdelivr.net/npm/wabt@1.0.32/index.js"></script>
    <script>
        let wabt = null, mem = null;
        
        async function init() {{ if (!wabt) wabt = await WabtModule(); return wabt; }}
        
        async function run() {{
            const out = document.getElementById('output');
            out.textContent = 'Kör...\n';
            try {{
                const mod = await init().then(w => w.parseWat('h.wat', document.getElementById('code').textContent));
                const bin = mod.toBinary({{}});
                const {{ instance }} = await WebAssembly.instantiate(bin.buffer, {{
                    wasi_snapshot_preview1: {{
                        fd_write: (fd, p, l) => {{
                            if (fd === 1) {{
                                const d = new Uint8Array(mem.buffer);
                                let n = 0;
                                while (p + n < d.length && d[p + n]) n++;
                                out.textContent += new TextDecoder().decode(d.slice(p, p + n));
                            }}
                            return 0;
                        }}
                    }}
                }});
                mem = instance.exports.memory;
                if (instance.exports._start) instance.exports._start();
                out.textContent += '\\nKlart!';
            }} catch (e) {{ out.textContent += '\\nFel: ' + e.message; }}
        }}
        
        function toggle() {{
            const c = document.getElementById('code');
            c.style.display = c.style.display === 'none' ? 'block' : 'none';
        }}
        
        function clear() {{ document.getElementById('output').textContent = ''; }}
    </script>
</body>
</html>'''

def main():
    src = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1]).read()
    
    tokens = tokenize(src)
    stmts = parse(tokens)
    wat = compile_to_wasm(stmts)
    html = create_html(wat)
    
    out = sys.argv[2] if len(sys.argv) > 2 else 'hiuh.html'
    open(out, 'w').write(html)
    print(f"Kompilerade till {out}")

if __name__ == '__main__':
    main()