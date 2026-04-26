#!/usr/bin/env python3
"""
HIUH Native Compiler - x86_64 assembly
Simple register-based variable allocation
"""

import sys
import subprocess
import tempfile
import os

def tokenize(src):
    tokens = []
    for line in src.split('\n'):
        stripped = line.lstrip()
        if not stripped:
            continue
        words = stripped.split()
        first = words[0]
        
        if first == 'Skriv':
            rest = ' '.join(words[1:])
            if rest.startswith('värdet av '):
                tokens.append(('SKRIV_VAR', words[-1]))
            else:
                tokens.append(('SKRIV', rest))
        elif first == '.':
            # Comment line - skip
            continue
        elif first == 'Sätt' and len(words) >= 4:
            var = words[1]
            rest = ' '.join(words[3:])
            if 'pluss' in rest:
                parts = rest.split('pluss')
                left = parts[0].strip()
                right = parts[1].strip() if len(parts) > 1 else '0'
                tokens.append(('PLUS', var, left, right))
            else:
                tokens.append(('SET', var, rest))
        elif first == 'För':
            var = words[1] if len(words) > 1 else 'i'
            try:
                fi = words.index('från')
                ti = words.index('till')
                start = words[fi+1]
                end = words[ti+1]
            except:
                start, end = '0', '10'
            tokens.append(('FOR', var, start, end))
        elif first == 'Hejdå':
            tokens.append(('END',))
        elif first == 'JagMåsteGåNu':
            code = words[1] if len(words) > 1 and words[1].isdigit() else '0'
            tokens.append(('EXIT', code))
        
        elif first == 'Läs':
            tokens.append(('READ',))
        
        elif first == 'tecken':
            # "tecken <index> ur <source>" - get char at index from source
            try:
                ur_idx = words.index('ur')
                if ur_idx > 1:
                    idx_var = words[ur_idx - 1]
                    source = ' '.join(words[ur_idx+1:]) if ur_idx+1 < len(words) else ''
                    tokens.append(('CHAR_AT', idx_var, source))
            except:
                pass
        
        elif first == 'hämta':
            # "hämta element <index> från <list>" - get element at index from list
            try:
                element_idx = words.index('element')
                från_idx = words.index('från')
                if element_idx > 0 and från_idx > element_idx:
                    idx_var = words[element_idx + 1]
                    list_name = ' '.join(words[från_idx+1:]) if från_idx+1 < len(words) else ''
                    tokens.append(('LIST_GET', idx_var, list_name))
            except:
                pass
        
        elif first == 'Om':
            # "Om x är mindre än y" → store comparison type with IF
            rest = words[1:]
            cmp_type = 'EQ'
            if 'mindre' in words and 'än' in words:
                cmp_type = 'LT'
            elif 'större' in words and 'än' in words:
                cmp_type = 'GT'
            elif 'är' in words:
                cmp_type = 'EQ'
            if len(rest) >= 2:
                var1 = rest[0]
                var2 = rest[-1]
                tokens.append(('IF', cmp_type, var1, var2))
            else:
                tokens.append(('IF',))
        
        elif first == 'Annars':
            # ELSE is handled by the IF parser - don't create token here
            # Just mark that we're in an else block for the next Skriv/etc
            tokens.append(('ELSE',))
        
        elif 'är' in words and 'mindre' in words and 'än' in words:
            # "x är mindre än y" → CMP_LT
            var1 = words[0]
            var2 = words[-1]
            tokens.append(('CMP_LT', var1, var2))
        
        elif 'är' in words and 'större' in words and 'än' in words:
            # "x är större än y" → CMP_GT
            var1 = words[0]
            var2 = words[-1]
            tokens.append(('CMP_GT', var1, var2))
        
        elif first == 'är':
            # "x är y" comparison
            var1 = words[0]
            var2 = words[2] if len(words) > 2 else '0'
            tokens.append(('CMP_EQ', var1, var2))
        
        elif first == 'Lägg' and len(words) >= 5:
            if words[1] == 'till':
                item = words[2]
                target = words[4]
                tokens.append(('APPEND', item, target))
    return tokens

def parse(tokens):
    stmts = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok[0] == 'SKRIV':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'SKRIV_VAR':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'SET':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'PLUS':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'FOR':
            body = []
            i += 1
            while i < len(tokens) and tokens[i][0] != 'END':
                body.append(tokens[i])
                i += 1
            if i < len(tokens) and tokens[i][0] == 'END':
                i += 1
            stmts.append(('FOR', tok[1], tok[2], tok[3], body))
        elif tok[0] == 'EXIT':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'READ':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'CHAR_AT':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'APPEND':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'LIST_GET':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'IF':
            # Check for upcoming ELSE
            has_else = False
            for j in range(i+1, len(tokens)):
                if tokens[j][0] == 'ELSE':
                    has_else = True
                    break
                if tokens[j][0] == 'END':
                    break
            
            # Generate comparison first (from tok[1:4])
            cmp_info = None
            if len(tok) >= 4:
                cmp_type, var1, var2 = tok[1], tok[2], tok[3]
                cmp_info = (cmp_type, var1, var2)
                if cmp_type == 'LT':
                    stmts.append(('CMP_LT', var1, var2))
                elif cmp_type == 'GT':
                    stmts.append(('CMP_GT', var1, var2))
                else:
                    stmts.append(('CMP', var1, var2))
            
            # Parse IF body
            body = []
            i += 1
            while i < len(tokens) and tokens[i][0] not in ('END', 'ELSE'):
                body.append(tokens[i])
                i += 1
            
            if has_else:
                # IF with ELSE
                stmts.append(('IF', body, cmp_info, '__HAS_ELSE__'))
                if i < len(tokens) and tokens[i][0] == 'ELSE':
                    i += 1  # skip ELSE token
                    else_body = []
                    while i < len(tokens) and tokens[i][0] != 'END':
                        else_body.append(tokens[i])
                        i += 1
                    if i < len(tokens) and tokens[i][0] == 'END':
                        i += 1
                    stmts.append(('ELSE', else_body))
            else:
                # Plain IF
                stmts.append(('IF', body, cmp_info))
                if i < len(tokens) and tokens[i][0] == 'END':
                    i += 1
        
        elif tok[0] == 'CMP':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'CMP_LT':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'CMP_GT':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'ELSE':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'END':
            i += 1
        else:
            i += 1
    return stmts

def compile_to_asm(stmts):
    code = []
    data = []
    strings = []
    
    var_reg = {}
    next_reg = 0
    reg_names = ['%r12', '%r13', '%r14', '%r15']
    labels = [0]
    
    def alloc_var(v):
        nonlocal next_reg
        if v not in var_reg:
            var_reg[v] = reg_names[next_reg % 4]
            next_reg += 1
        return var_reg[v]
    
    def new_label():
        labels[0] += 1
        return f'L{labels[0]}'
    
    def resolve(v):
        # Special case: 'tecken' is always in r15 (last CHAR_AT result)
        if v == 'tecken' or v == '_tecken':
            return '%r15'
        try:
            return f'${int(v)}'
        except:
            if v in var_reg:
                return var_reg[v]
            return '%r12'
    
    def compile_stmt(stmt):
        op = stmt[0]
        
        if op == 'SKRIV':
            s = stmt[1]
            strings.append(s)
            idx = len(strings) - 1
            code.append(f"    lea msg_{idx}(%rip), %rsi")
            code.append(f"    mov ${len(s)}, %edx")
            code.append(f"    mov $1, %edi")
            code.append(f"    mov $1, %eax")
            code.append(f"    syscall")
        
        elif op == 'SKRIV_VAR':
            reg = var_reg.get(stmt[1], '%r12')
            code.append(f"    mov {reg}, %r12  # print {stmt[1]}")
            # Store value in buffer and print
            code.append(f"    lea num_buf(%rip), %rsi")
            code.append(f"    mov %r12b, (%rsi)")
            code.append(f"    mov $1, %rdx")
            code.append(f"    mov $1, %rdi")
            code.append(f"    mov $1, %eax")
            code.append(f"    syscall")
        
        elif op == 'SET':
            var = stmt[1]
            val = stmt[2]
            reg = alloc_var(var)
            r = resolve(val)
            code.append(f"    mov {r}, {reg}  # {var} = {val}")
        
        elif op == 'PLUS':
            var = stmt[1]
            left = stmt[2]
            right = stmt[3]
            reg = alloc_var(var)
            r1 = resolve(left)
            r2 = resolve(right)
            code.append(f"    mov {r1}, %rcx  # {var} = {left} + {right}")
            code.append(f"    add {r2}, %rcx")
            code.append(f"    mov %rcx, {reg}")
        
        elif op == 'FOR':
            var = stmt[1]
            start = stmt[2]
            end = stmt[3]
            body = stmt[4]
            
            reg = alloc_var(var)
            loop_start = new_label()
            loop_end = new_label()
            
            # Resolve start and end values
            start_r = resolve(start)
            end_r = resolve(end)
            
            code.append(f"    mov {start_r}, {reg}  # for {var}")
            code.append(f"{loop_start}:")
            code.append(f"    mov {end_r}, %rax")
            code.append(f"    cmp %rax, {reg}")
            code.append(f"    jge {loop_end}")
            
            for s in body:
                compile_stmt(s)
            
            code.append(f"    inc {reg}")
            code.append(f"    jmp {loop_start}")
            code.append(f"{loop_end}:")
        
        elif op == 'IF':
            print(f"DEBUG compile IF: stmt={stmt}")
            # stmt = ('IF', body, cmp_info) or ('IF', body, cmp_info, '__HAS_ELSE__')
            has_else = len(stmt) > 3 and stmt[3] == '__HAS_ELSE__'
            body = stmt[1]
            cmp_info = stmt[2] if len(stmt) > 2 else None
            if_end = new_label()
            code.append(f"    cmp $0, %al  # if")
            code.append(f"    je {if_end}")
            for s in body:
                compile_stmt(s)
            if has_else:
                else_end = new_label()
                code.append(f"    jmp {else_end}")
                code.append(f"{if_end}:")
            else:
                code.append(f"{if_end}:")
        
        elif op == 'EXIT':
            code.append(f"    mov ${stmt[1]}, %edi")
            code.append(f"    mov $60, %rax")
            code.append(f"    syscall")
        
        elif op == 'ELSE':
            # ELSE body - execute unconditionally after IF
            body = stmt[1] if len(stmt) > 1 else []
            for s in body:
                compile_stmt(s)
            # Add ELSE end label (referenced by IF's jmp)
            else_end = new_label()
            code.append(f"{else_end}:")
        
        elif op == 'APPEND':
            item, target = stmt[1], stmt[2]
            if item in var_reg:
                code.append(f"    mov {var_reg[item]}, %r15  # append {item}")
                code.append(f"    mov %r15, (%r14)")
                code.append(f"    inc %r14")
        
        elif op == 'LIST_GET':
            idx, list_name = stmt[1], stmt[2]
            code.append(f"    # hämta element {idx} från {list_name} → r15")
            code.append(f"    mov $0, %r15  # TODO: implement LIST_GET")
        
        elif op == 'CMP':
            var1, var2 = stmt[1], stmt[2]
            r1 = var_reg.get(var1, '%r12')
            r2 = var_reg.get(var2, '%r12')
            code.append(f"    mov {r2}, %rax  # cmp {var1} == {var2}")
            code.append(f"    cmp {r1}, %rax")
            code.append(f"    sete %al")
        
        elif op == 'CMP_LT':
            # "x är mindre än y" → var1 < var2
            var1, var2 = stmt[1], stmt[2]
            r1 = resolve(var1)
            r2 = resolve(var2)
            code.append(f"    mov {r1}, %rax  # cmp_lt {var1} < {var2}")
            code.append(f"    cmp {r2}, %rax")
            code.append(f"    setl %al")
        
        elif op == 'CMP_GT':
            # "x är större än y" → var1 > var2
            var1, var2 = stmt[1], stmt[2]
            r1 = resolve(var1)
            r2 = resolve(var2)
            code.append(f"    mov {r1}, %rax  # cmp_gt {var1} > {var2}")
            code.append(f"    cmp {r2}, %rax")
            code.append(f"    setg %al")
        
        elif op == 'READ':
            # Read from stdin into input_buf
            code.append(f"    mov $0, %eax  # read")
            code.append(f"    mov $0, %edi  # stdin")
            code.append(f"    lea input_buf(%rip), %rsi")
            code.append(f"    mov $256, %edx  # max bytes")
            code.append(f"    syscall")
        
        elif op == 'CHAR_AT':
            idx, var = stmt[1], stmt[2]
            # Get character at index from input_buf, store in r15 (not r12)
            if idx in var_reg:
                code.append(f"    mov {var_reg[idx]}, %rcx  # index")
            else:
                try:
                    code.append(f"    mov ${int(idx)}, %rcx  # index")
                except:
                    code.append(f"    mov $0, %rcx  # index fallback")
            code.append(f"    lea input_buf(%rip), %rsi")
            code.append(f"    add %rcx, %rsi")
            code.append(f"    mov (%rsi), %r15b  # character at index")
            # Track last char in a pseudo-variable
            var_reg['_tecken'] = '%r15'
            var_reg['tecken'] = '%r15'  # also as "tecken" for compatibility
    
    has_exit = False
    for stmt in stmts:
        compile_stmt(stmt)
        if stmt[0] == 'EXIT':
            has_exit = True
    
    if not has_exit:
        code.append(f"    mov $0, %edi")
        code.append(f"    mov $60, %rax")
        code.append(f"    syscall")
    
    data.append(".data")
    for i, s in enumerate(strings):
        escaped = s.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
        data.append(f"msg_{i}: .ascii \"{escaped}\\n\\0\"")
    data.append("num_buf: .byte 0")
    data.append("input_buf: .skip 256")
    data.append(".bss")
    data.append(".align 8")
    data.append("stack: .skip 4096")
    
    out = []
    out.append(".text")
    out.append(".globl _start")
    out.append("_start:")
    # Initialize stack pointer
    out.append("    lea stack(%rip), %r14  # init stack ptr")
    out.extend(code)
    out.append("")
    out.extend(data)
    
    return '\n'.join(out)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 hiuh-native.py <input.hiuh> [output]")
        return
    
    if sys.argv[1] == '-' or sys.argv[1] == '--stdin':
        src = sys.stdin.read()
    else:
        src = open(sys.argv[1]).read()
    
    tokens = tokenize(src)
    stmts = parse(tokens)
    asm = compile_to_asm(stmts)
    
    if '--asm' in sys.argv:
        print(asm)
        return
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.s', delete=False) as f:
        f.write(asm)
        asm_file = f.name
    
    obj_file = asm_file + '.o'
    output = sys.argv[2] if len(sys.argv) > 2 else './hiuh-runner'
    
    try:
        r = subprocess.run(['as', '-o', obj_file, asm_file], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"as error:\n{r.stderr}")
            return
        
        r = subprocess.run(['ld', '-o', output, obj_file], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"ld error:\n{r.stderr}")
            return
        
        import stat
        os.chmod(output, os.stat(output).st_mode | stat.S_IXUSR)
        print(f"Kompilerade till {output}")
    finally:
        for f in [asm_file, obj_file]:
            if os.path.exists(f):
                os.unlink(f)

if __name__ == '__main__':
    main()