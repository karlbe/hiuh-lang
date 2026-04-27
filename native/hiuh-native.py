#!/usr/bin/env python3
"""
HIUH Native Compiler - x86_64 assembly
Simple register-based variable allocation
"""

import sys
import subprocess
import tempfile
import os
import configparser

def load_config():
    cfg = configparser.ConfigParser()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg.read([os.path.join(script_dir, 'hiuh.cfg'), 'hiuh.cfg'])
    tools = cfg['tools'] if 'tools' in cfg else {}
    return {
        'as': tools.get('as', 'as'),
        'ld': tools.get('ld', 'ld'),
    }

CONFIG = load_config()

def tokenize(src):
    tokens = []
    ord_lista = []  # Word list for self-compilation
    
    for line in src.split('\n'):
        stripped = line.lstrip()
        if not stripped:
            continue
        words = stripped.split()
        first = words[0]
        
        # Save all non-comment words to ord_lista
        if first != '.':
            ord_lista.extend(words)
        
        if first in ('Skriv', 'SkrivNyRad'):
            rest = ' '.join(words[1:])
            nl = first == 'SkrivNyRad'
            if rest.startswith('värdet av '):
                tokens.append(('SKRIV_VAR_NL' if nl else 'SKRIV_VAR', words[-1]))
            elif rest.startswith('text i '):
                tokens.append(('SKRIV_BUF_NL' if nl else 'SKRIV_BUF', rest[len('text i '):]))
            else:
                tokens.append(('SKRIV_NL' if nl else 'SKRIV', rest))
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
            elif rest.startswith('grej med '):
                # Function definition: Sätt foo till grej med x, y
                params_str = rest[len('grej med '):]
                params = [p.strip() for p in params_str.split(',')]
                tokens.append(('FUNC_DEF', var, params))
            elif rest.startswith('Jämför ') and ' med ' in rest:
                # Sätt x till Jämför buf med lit
                rw = rest.split()
                med_i = rw.index('med')
                buf = rw[1]
                lit = rw[med_i + 1] if med_i + 1 < len(rw) else ''
                if buf and lit:
                    tokens.append(('CMP_BUF_LIT', var, buf, lit))
            elif rest.startswith('JämförBuffer ') and ' med ' in rest:
                # Sätt x till JämförBuffer buf1 med buf2
                rw = rest.split()
                med_i = rw.index('med')
                buf1 = rw[1]
                buf2 = rw[med_i + 1] if med_i + 1 < len(rw) else ''
                if buf1 and buf2:
                    tokens.append(('CMP_BUF_BUF', var, buf1, buf2))
            elif ' med ' in rest and not rest.startswith('grej '):
                # Function call: Sätt a till min med 2, 3
                parts = rest.split(' med ')
                func_name = parts[0].strip()
                args = [a.strip() for a in parts[1].split(',')]
                tokens.append(('FUNC_CALL', var, func_name, args))
            elif rest.startswith('tecken ') and ' ur ' in rest:
                # CHAR_AT: Sätt tecken till tecken i ur källa
                parts = rest.split(' ur ')
                if len(parts) >= 2:
                    idx_part = parts[0].replace('tecken', '').strip()
                    source = parts[1].strip()
                    tokens.append(('SET_CHAR_AT', var, idx_part, source))
                else:
                    tokens.append(('SET', var, rest))
            elif ' är ' in rest and ' pluss ' not in rest and ' med ' not in rest:
                parts = rest.split(' är ', 1)
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    if right.startswith('mindre än '):
                        tokens.append(('CMP_LT', left, right[len('mindre än '):].strip()))
                        tokens.append(('SET_CMP_RESULT', var))
                    elif right.startswith('större än '):
                        tokens.append(('CMP_GT', left, right[len('större än '):].strip()))
                        tokens.append(('SET_CMP_RESULT', var))
                    else:
                        tokens.append(('CMP', left, right))
                        tokens.append(('SET_CMP_RESULT', var))
                else:
                    tokens.append(('SET', var, rest))
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
        elif first == 'ge':
            # Return statement: ge x
            val = words[1] if len(words) > 1 else '0'
            tokens.append(('RETURN', val))
        
        elif first == 'Bryt':
            tokens.append(('BREAK',))

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
        
        elif first == 'Lagra':
            # Lagra X vid Y i Z → STORE_CHAR X Y Z
            if len(words) >= 6 and words[2] == 'vid' and words[4] == 'i':
                tokens.append(('STORE_CHAR', words[1], words[3], words[5]))

        elif first == 'Jämför':
            # Standalone Jämför X med Y — implicit träff target (legacy form)
            if 'med' in words:
                med_i = words.index('med')
                buf = words[1] if med_i > 1 else ''
                lit = words[med_i + 1] if med_i + 1 < len(words) else ''
                if buf and lit:
                    tokens.append(('CMP_BUF_LIT', 'träff', buf, lit))

        elif first == 'JämförBuffer':
            # Standalone JämförBuffer X med Y — implicit träff target (legacy form)
            if 'med' in words:
                med_i = words.index('med')
                buf1 = words[1] if med_i > 1 else ''
                buf2 = words[med_i + 1] if med_i + 1 < len(words) else ''
                if buf1 and buf2:
                    tokens.append(('CMP_BUF_BUF', 'träff', buf1, buf2))

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
                # For "är mindre än" / "är större än", var2 is the word after 'än'
                if 'än' in words:
                    än_idx = words.index('än')
                    var2 = words[än_idx + 1] if än_idx + 1 < len(words) else rest[-1]
                else:
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
            # "x är y" → SET x y (simple assignment, not comparison)
            var1 = words[0]
            var2 = words[2] if len(words) > 2 else '0'
            tokens.append(('SET', var1, var2))
        
        elif 'är' in words and 'pluss' in words:
            # "x är y pluss z" → PLUS x y z
            var = first
            parts = words[words.index('är')+1:]
            pluss_idx = parts.index('pluss')
            left = ' '.join(parts[:pluss_idx]).strip()
            right = ' '.join(parts[pluss_idx+1:]).strip()
            tokens.append(('PLUS', var, left, right))
        
        elif 'är' in words and first != 'är':
            # "x är y" → SET x y (when first is not 'är')
            var = first
            idx = words.index('är')
            val = words[idx+1] if idx+1 < len(words) else '0'
            tokens.append(('SET', var, val))
        
        elif first == 'Lägg' and len(words) >= 5:
            if words[1] == 'till':
                item = words[2]
                target = words[4]
                tokens.append(('APPEND', item, target))
    return tokens, ord_lista

def parse(tokens):
    def parse_block(pos):
        blk = []
        i = pos
        while i < len(tokens) and tokens[i][0] != 'END':
            tok = tokens[i]
            if tok[0] == 'IF':
                if len(tok) >= 4:
                    cmp_type, v1, v2 = tok[1], tok[2], tok[3]
                    if cmp_type == 'LT':
                        blk.append(('CMP_LT', v1, v2))
                    elif cmp_type == 'GT':
                        blk.append(('CMP_GT', v1, v2))
                    else:
                        blk.append(('CMP', v1, v2))
                i += 1
                if_body, i = parse_block(i)
                # check for ELSE
                if i < len(tokens) and tokens[i][0] == 'ELSE':
                    i += 1
                    else_body, i = parse_block(i)
                    blk.append(('IF', if_body, '__HAS_ELSE__'))
                    blk.append(('ELSE', else_body))
                else:
                    blk.append(('IF', if_body))
            elif tok[0] == 'FOR':
                i += 1
                inner, i = parse_block(i)
                blk.append(('FOR', tok[1], tok[2], tok[3], inner))
            else:
                blk.append(tok)
                i += 1
        if i < len(tokens) and tokens[i][0] == 'END':
            i += 1
        return blk, i

    stmts = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok[0] in ('SKRIV', 'SKRIV_NL'):
            stmts.append(tok)
            i += 1
        elif tok[0] in ('SKRIV_VAR', 'SKRIV_VAR_NL'):
            stmts.append(tok)
            i += 1
        elif tok[0] == 'SET':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'SET_CHAR_AT':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'SET_CMP_RESULT':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'STORE_CHAR':
            stmts.append(tok)
            i += 1
        elif tok[0] in ('CMP_BUF_LIT', 'CMP_BUF_BUF'):
            stmts.append(tok)
            i += 1
        elif tok[0] in ('SKRIV_BUF', 'SKRIV_BUF_NL'):
            stmts.append(tok)
            i += 1
        elif tok[0] == 'PLUS':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'FOR':
            i += 1
            body, i = parse_block(i)
            stmts.append(('FOR', tok[1], tok[2], tok[3], body))
        elif tok[0] == 'EXIT':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'READ':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'BREAK':
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
        elif tok[0] == 'FUNC_DEF':
            # Parse function body until END, handling nested IF-ELSE
            body = []
            i += 1
            depth = 1
            while i < len(tokens) and depth > 0:
                tok2 = tokens[i]
                if tok2[0] == 'IF':
                    # Handle IF with body until ELSE or END
                    has_else = False
                    for j in range(i+1, len(tokens)):
                        if tokens[j][0] == 'ELSE':
                            has_else = True
                            break
                        if tokens[j][0] == 'END':
                            break
                    # Generate CMP statement
                    if len(tok2) >= 4:
                        cmp_type, var1, var2 = tok2[1], tok2[2], tok2[3]
                        if cmp_type == 'LT':
                            body.append(('CMP_LT', var1, var2))
                        elif cmp_type == 'GT':
                            body.append(('CMP_GT', var1, var2))
                        else:
                            body.append(('CMP', var1, var2))
                    # Parse IF body with depth tracking
                    if_body = []
                    i += 1
                    depth += 1
                    while depth > 1:
                        tok3 = tokens[i]
                        if tok3[0] == 'IF':
                            depth += 1
                            if_body.append(tok3)
                            i += 1
                        elif tok3[0] == 'END':
                            depth -= 1
                            if depth > 1:
                                if_body.append(tok3)
                            i += 1
                        elif tok3[0] == 'ELSE' and depth == 2:
                            # End of IF body, start of ELSE body
                            i += 1
                            else_body = []
                            while depth > 1:
                                tok4 = tokens[i]
                                if tok4[0] == 'IF':
                                    depth += 1
                                    else_body.append(tok4)
                                    i += 1
                                elif tok4[0] == 'END':
                                    depth -= 1
                                    if depth > 1:
                                        else_body.append(tok4)
                                    i += 1
                                elif tok4[0] == 'RETURN' and depth == 2:
                                    # End of function body
                                    else_body.append(tok4)
                                    body.append(('IF', if_body, else_body, '__HAS_ELSE__'))
                                    i += 1
                                    depth = 0  # Exit function
                                    break
                        else:
                            if_body.append(tok3)
                            i += 1
                    continue
                elif tok2[0] == 'END':
                    depth -= 1
                    if depth > 0:
                        body.append(tok2)
                    i += 1
                elif tok2[0] == 'RETURN' and depth == 1:
                    # End of function body
                    body.append(tok2)
                    i += 1
                    depth = 0
                    break
                else:
                    if tok2[0] == 'FOR':
                        # Recursively parse nested FOR
                        inner_body = []
                        i += 1
                        while i < len(tokens) and tokens[i][0] != 'END':
                            inner_body.append(tokens[i])
                            i += 1
                        if i < len(tokens) and tokens[i][0] == 'END':
                            i += 1
                        # The inner FOR still needs parsing, add raw for now
                        body.append(('FOR', tok2[1], tok2[2], tok2[3], inner_body))
                    else:
                        body.append(tok2)
                        i += 1
            stmts.append(('FUNC', tok[1], tok[2], body))
        elif tok[0] == 'FUNC_CALL':
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

def compile_to_asm(stmts, target='linux'):
    code = []
    data = []
    strings = []
    
    var_reg = {}
    func_defs = {}  # Store function definitions
    next_reg = 0
    # r12-r15 for variables; r14=stack ptr, r15=char/temp (reserved)
    reg_names = ['%r12', '%r13', '%r8', '%r9', '%r10', '%r11']  # 6 vars max
    # Track reserved registers
    reserved = {'%r14': 'stack pointer', '%r15': 'temp/char result'}
    labels = [0]
    loop_labels = []  # stack of loop_end labels for Bryt (break)
    named_buffers = set()
    skriv_buf_used = [False]
    fmt_s_used = [False]       # "%s" format string for no-newline printf
    fmt_int_nonl_used = [False]  # "%lld" format string (no newline)
    lit_strings = []
    strings_nonl = []  # strings for SKRIV (no newline)

    def alloc_var(v):
        nonlocal next_reg
        if v not in var_reg:
            reg = reg_names[next_reg % 6]
            # Never allocate reserved registers
            while reg in reserved:
                next_reg += 1
                reg = reg_names[next_reg % 6]
            var_reg[v] = reg
            next_reg += 1
        return var_reg[v]
    
    def new_label():
        labels[0] += 1
        return f'L{labels[0]}'
    
    def resolve(v):
        # Handle 'tecken' - if explicitly stored in a register, use that; otherwise use r15
        if v == 'tecken' or v == '_tecken':
            if v in var_reg:
                return var_reg[v]
            return '%r15'
        # Check if it's a number
        try:
            return f'${int(v)}'
        except:
            pass
        # Look up variable in register allocation
        if v in var_reg:
            return var_reg[v]
        return '%r12'  # Default
    
    def win_call_save(exclude=None):
        cs = {'%r8', '%r9', '%r10', '%r11'}
        to_save = sorted(r for r in var_reg.values() if r in cs and r != exclude)
        align_pad = 8 if len(to_save) % 2 == 1 else 0
        if align_pad:
            code.append(f"    subq $8, %rsp  # alignment pad")
        for reg in to_save:
            code.append(f"    push {reg}")
        code.append(f"    subq $32, %rsp  # shadow space")
        return to_save, align_pad

    def win_call_restore(to_save, align_pad):
        code.append(f"    addq $32, %rsp")
        for reg in reversed(to_save):
            code.append(f"    pop {reg}")
        if align_pad:
            code.append(f"    addq $8, %rsp  # restore alignment pad")

    def compile_stmt(stmt):
        op = stmt[0]
        
        if op == 'SKRIV_NL':
            s = stmt[1]
            strings.append(s)
            idx = len(strings) - 1
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea msg_{idx}(%rip), %rcx")
                code.append(f"    call puts")
                win_call_restore(to_save, align_pad)
            else:
                code.append(f"    lea msg_{idx}(%rip), %rsi")
                code.append(f"    mov ${len(s) + 1}, %edx")
                code.append(f"    mov $1, %edi")
                code.append(f"    mov $1, %eax")
                code.append(f"    syscall")

        elif op == 'SKRIV':
            s = stmt[1]
            strings_nonl.append(s)
            idx = len(strings_nonl) - 1
            fmt_s_used[0] = True
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea fmt_s(%rip), %rcx")
                code.append(f"    lea msg_nonl_{idx}(%rip), %rdx")
                code.append(f"    call printf")
                win_call_restore(to_save, align_pad)
            else:
                code.append(f"    lea msg_nonl_{idx}(%rip), %rsi")
                code.append(f"    mov ${len(s)}, %edx")
                code.append(f"    mov $1, %edi")
                code.append(f"    mov $1, %eax")
                code.append(f"    syscall")
        
        elif op == 'SKRIV_VAR_NL':
            reg = resolve(stmt[1])
            if target == 'windows':
                if reg == '%r15':
                    code.append(f"    movzx %r15b, %rax  # save print value")
                else:
                    code.append(f"    mov {reg}, %rax  # save print value")
                to_save, align_pad = win_call_save()
                code.append(f"    mov %rax, %rdx")
                code.append(f"    lea fmt_int(%rip), %rcx")
                code.append(f"    call printf")
                win_call_restore(to_save, align_pad)
            else:
                if reg.startswith('$'):
                    code.append(f"    mov {reg}, %rax")
                    code.append(f"    lea num_buf(%rip), %rsi")
                    code.append(f"    mov %al, (%rsi)")
                elif reg == '%r15':
                    code.append(f"    lea num_buf(%rip), %rsi")
                    code.append(f"    mov %r15b, (%rsi)")
                else:
                    code.append(f"    lea num_buf(%rip), %rsi")
                    code.append(f"    mov {reg}, %al")
                    code.append(f"    mov %al, (%rsi)")
                code.append(f"    mov $1, %rdx")
                code.append(f"    mov $1, %rdi")
                code.append(f"    mov $1, %eax")
                code.append(f"    syscall")

        elif op == 'SKRIV_VAR':
            reg = resolve(stmt[1])
            fmt_int_nonl_used[0] = True
            if target == 'windows':
                if reg == '%r15':
                    code.append(f"    movzx %r15b, %rax  # save print value")
                else:
                    code.append(f"    mov {reg}, %rax  # save print value")
                to_save, align_pad = win_call_save()
                code.append(f"    mov %rax, %rdx")
                code.append(f"    lea fmt_int_nonl(%rip), %rcx")
                code.append(f"    call printf")
                win_call_restore(to_save, align_pad)
            else:
                if reg.startswith('$'):
                    code.append(f"    mov {reg}, %rax  # print {stmt[1]}")
                    code.append(f"    lea num_buf(%rip), %rsi")
                    code.append(f"    mov %al, (%rsi)")
                elif reg == '%r15':
                    code.append(f"    lea num_buf(%rip), %rsi")
                    code.append(f"    mov %r15b, (%rsi)")
                elif reg in ['%r12', '%r13', '%r8', '%r9', '%r10', '%r11']:
                    byte_reg = reg.replace('%r12', '%r12b').replace('%r13', '%r13b').replace('%r8', '%r8b').replace('%r9', '%r9b').replace('%r10', '%r10b').replace('%r11', '%r11b')
                    code.append(f"    lea num_buf(%rip), %rsi")
                    code.append(f"    mov {byte_reg}, (%rsi)")
                else:
                    code.append(f"    lea num_buf(%rip), %rsi")
                    code.append(f"    mov {reg}, %al")
                    code.append(f"    mov %al, (%rsi)")
                code.append(f"    mov $1, %rdx")
                code.append(f"    mov $1, %rdi")
                code.append(f"    mov $1, %eax")
                code.append(f"    syscall")
        
        elif op == 'SET':
            var = stmt[1]
            val = stmt[2]
            reg = alloc_var(var)
            r = resolve(val)
            code.append(f"    mov {r}, {reg}  # {var} = {val} (was val={val})")
        
        elif op == 'SET_CMP_RESULT':
            # Store result of previous CMP into target variable
            var = stmt[1]
            reg = alloc_var(var)
            # sete %al sets al to 1 if equal (ZF=1), 0 if not equal (ZF=0)
            # movzx %al to full register, then store
            code.append(f"    movzx %al, %rax  # extend sete result")
            code.append(f"    mov %rax, {reg}  # store comparison result")
        
        elif op == 'SET_CHAR_AT':
            var = stmt[1]
            idx = stmt[2]
            source = stmt[3]
            if var in ('tecken', '_tecken'):
                # Keep result in %r15 (reserved for char) — don't consume a GP register
                var_reg[var] = '%r15'
                compile_stmt(('CHAR_AT', idx, source))
                code.append(f"    movzx %r15b, %r15")
            else:
                reg = alloc_var(var)
                compile_stmt(('CHAR_AT', idx, source))
                code.append(f"    movzx %r15b, %r15")
                code.append(f"    mov %r15, {reg}  # {var} = tecken")
        
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

            # '_' is an anonymous counter — use %rbx (callee-saved, stable
            # across calls, not in the named variable pool)
            if var == '_':
                loop_start = new_label()
                loop_end = new_label()
                start_r = resolve(start)
                end_r = resolve(end)
                code.append(f"    push %rbx  # save caller's rbx")
                code.append(f"    mov {start_r}, %rbx  # for _")
                code.append(f"{loop_start}:")
                code.append(f"    mov {end_r}, %rax")
                code.append(f"    cmp %rax, %rbx")
                code.append(f"    jge {loop_end}")
                loop_labels.append(loop_end)
                for s in body:
                    compile_stmt(s)
                loop_labels.pop()
                code.append(f"    inc %rbx")
                code.append(f"    jmp {loop_start}")
                code.append(f"{loop_end}:")
                code.append(f"    pop %rbx  # restore caller's rbx")
            else:
                reg = alloc_var(var)
                loop_start = new_label()
                loop_end = new_label()
                start_r = resolve(start)
                end_r = resolve(end)
                code.append(f"    mov {start_r}, {reg}  # for {var}")
                code.append(f"{loop_start}:")
                code.append(f"    mov {end_r}, %rax")
                code.append(f"    cmp %rax, {reg}")
                code.append(f"    jge {loop_end}")
                loop_labels.append(loop_end)
                for s in body:
                    compile_stmt(s)
                loop_labels.pop()
                code.append(f"    inc {reg}")
                code.append(f"    jmp {loop_start}")
                code.append(f"{loop_end}:")
                
        elif op == 'IF':
            # stmt = ('IF', body, else_body, '__HAS_ELSE__') or ('IF', body)
            # '__HAS_ELSE__' is now at the END of the tuple, not in the middle
            has_else = len(stmt) > 3 and stmt[-1] == '__HAS_ELSE__'
            if has_else:
                body = stmt[1]
                else_body = stmt[2]
            else:
                body = stmt[1]
                else_body = None
            if_end = new_label()
            code.append(f"    cmp $0, %al  # if")
            code.append(f"    je {if_end}")
            for s in body:
                compile_stmt(s)
            if has_else:
                else_end = new_label()
                code.append(f"    jmp {else_end}")
                code.append(f"{if_end}:")
                # Compile the ELSE body
                for s in else_body:
                    compile_stmt(s)
                code.append(f"{else_end}:")
            else:
                code.append(f"{if_end}:")
        
        elif op == 'BREAK':
            if loop_labels:
                code.append(f"    jmp {loop_labels[-1]}  # Bryt")

        elif op == 'EXIT':
            if target == 'windows':
                code.append(f"    mov ${stmt[1]}, %ecx")
                code.append(f"    call exit")
            else:
                code.append(f"    mov ${stmt[1]}, %edi")
                code.append(f"    mov $60, %rax")
                code.append(f"    syscall")
        
        elif op == 'FUNC':
            # Store function definition for later use
            # stmt = (FUNC, name, params, body)
            func_defs[stmt[1]] = stmt
        
        elif op == 'FUNC_CALL':
            var, func_name, args = stmt[1], stmt[2], stmt[3]
            # Simple: inline the function body with args bound to temps
            if func_name in func_defs:
                func = func_defs[func_name]
                params = func[2]
                body = func[3]
                # Bind params to args
                for p, a in zip(params, args):
                    compile_stmt(('SET', p, a))
                # Compile body (stop at RETURN)
                for s in body:
                    if s[0] == 'RETURN':
                        # Store return value in special register
                        ret_val = s[1]
                        ret_reg = resolve(ret_val)
                        code.append(f"    mov {ret_reg}, %r11  # _result")
                        break
                    compile_stmt(s)
            # Store result in var
            reg = alloc_var(var)
            code.append(f"    mov %r11, {reg}  # {var} = _result")
        
        elif op == 'ELSE':
            # ELSE body - execute unconditionally after IF
            body = stmt[1] if len(stmt) > 1 else []
            for s in body:
                compile_stmt(s)
            # Add ELSE end label (referenced by IF's jmp)
            else_end = new_label()
            code.append(f"{else_end}:")
        
        elif op == 'APPEND':
            item, dest = stmt[1], stmt[2]
            r = resolve(item)
            code.append(f"    mov {r}, %r15  # append {item}")
            code.append(f"    mov %r15, (%r14)")
            code.append(f"    inc %r14")
        
        elif op == 'LIST_GET':
            idx, list_name = stmt[1], stmt[2]
            # Get index into rax
            if idx in var_reg:
                code.append(f"    mov {var_reg[idx]}, %rax  # LIST_GET index")
            else:
                try:
                    code.append(f"    mov ${int(idx)}, %rax  # LIST_GET index literal")
                except:
                    code.append(f"    mov $0, %rax  # LIST_GET index fallback")
            # Calculate address = stack_base + index
            code.append(f"    lea stack(%rip), %rsi  # LIST_GET base")
            code.append(f"    add %rax, %rsi")
            # Load byte into r13 (not r15, to avoid conflict with CHAR_AT)
            code.append(f"    mov (%rsi), %r13b  # hämta element")
            # Track as "tecken" variable
            var_reg['tecken'] = '%r13'
            var_reg['_tecken'] = '%r13'
        
        elif op == 'CMP':
            var1, var2 = stmt[1], stmt[2]
            r1 = var_reg.get(var1, '%r12')
            # Handle numeric literals
            try:
                val2 = int(var2)
                code.append(f"    mov {r1}, %rax  # cmp {var1} == {var2}")
                code.append(f"    cmp ${val2}, %rax")
            except ValueError:
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
            if target == 'windows':
                code.append(f"    lea input_buf(%rip), %rax")
                code.append(f"    movb $0, (%rax)  # pre-zero: 0 on EOF after fgets")
                code.append(f"    mov $0, %ecx")
                code.append(f"    call __acrt_iob_func  # get stdin FILE*")
                code.append(f"    mov %rax, %r8")
                code.append(f"    lea input_buf(%rip), %rcx")
                code.append(f"    mov $256, %edx")
                code.append(f"    call fgets")
            else:
                code.append(f"    lea input_buf(%rip), %rax")
                code.append(f"    movb $0, (%rax)  # pre-zero: 0 on EOF after read")
                code.append(f"    mov $0, %eax  # read")
                code.append(f"    mov $0, %edi  # stdin")
                code.append(f"    lea input_buf(%rip), %rsi")
                code.append(f"    mov $256, %edx  # max bytes")
                code.append(f"    syscall")
        
        elif op == 'CMP_BUF_LIT':
            target_var, buf_name, literal = stmt[1], stmt[2], stmt[3]
            lit_strings.append(literal)
            lit_idx = len(lit_strings) - 1
            träff_reg = alloc_var(target_var)
            if target == 'windows':
                to_save, align_pad = win_call_save(exclude=träff_reg)
                code.append(f"    lea {buf_name}(%rip), %rcx")
                code.append(f"    lea lit_{lit_idx}(%rip), %rdx")
                code.append(f"    call strcmp")
                code.append(f"    test %eax, %eax")
                code.append(f"    sete %al")
                win_call_restore(to_save, align_pad)
                code.append(f"    movzx %al, %rax")
                code.append(f"    mov %rax, {träff_reg}  # träff = strcmp result")
            else:
                # Inline strcmp: rsi=buf, rdi=lit → result in träff_reg
                lbl_loop = new_label()
                lbl_ne = new_label()
                lbl_eq = new_label()
                lbl_done = new_label()
                code.append(f"    lea {buf_name}(%rip), %rsi")
                code.append(f"    lea lit_{lit_idx}(%rip), %rdi")
                code.append(f"{lbl_loop}:")
                code.append(f"    movb (%rsi), %al")
                code.append(f"    movb (%rdi), %cl")
                code.append(f"    cmpb %cl, %al")
                code.append(f"    jne {lbl_ne}")
                code.append(f"    testb %al, %al")
                code.append(f"    jz {lbl_eq}")
                code.append(f"    inc %rsi")
                code.append(f"    inc %rdi")
                code.append(f"    jmp {lbl_loop}")
                code.append(f"{lbl_eq}:")
                code.append(f"    mov $1, %rax")
                code.append(f"    jmp {lbl_done}")
                code.append(f"{lbl_ne}:")
                code.append(f"    xor %rax, %rax")
                code.append(f"{lbl_done}:")
                code.append(f"    mov %rax, {träff_reg}  # träff = strcmp result")

        elif op == 'CMP_BUF_BUF':
            target_var, buf1, buf2 = stmt[1], stmt[2], stmt[3]
            named_buffers.add(buf1)
            named_buffers.add(buf2)
            träff_reg = alloc_var(target_var)
            if target == 'windows':
                to_save, align_pad = win_call_save(exclude=träff_reg)
                code.append(f"    lea {buf1}(%rip), %rcx")
                code.append(f"    lea {buf2}(%rip), %rdx")
                code.append(f"    call strcmp")
                code.append(f"    test %eax, %eax")
                code.append(f"    sete %al")
                win_call_restore(to_save, align_pad)
                code.append(f"    movzx %al, %rax")
                code.append(f"    mov %rax, {träff_reg}  # träff = strcmp result")
            else:
                lbl_loop = new_label()
                lbl_ne = new_label()
                lbl_eq = new_label()
                lbl_done = new_label()
                code.append(f"    lea {buf1}(%rip), %rsi")
                code.append(f"    lea {buf2}(%rip), %rdi")
                code.append(f"{lbl_loop}:")
                code.append(f"    movb (%rsi), %al")
                code.append(f"    movb (%rdi), %cl")
                code.append(f"    cmpb %cl, %al")
                code.append(f"    jne {lbl_ne}")
                code.append(f"    testb %al, %al")
                code.append(f"    jz {lbl_eq}")
                code.append(f"    inc %rsi")
                code.append(f"    inc %rdi")
                code.append(f"    jmp {lbl_loop}")
                code.append(f"{lbl_eq}:")
                code.append(f"    mov $1, %rax")
                code.append(f"    jmp {lbl_done}")
                code.append(f"{lbl_ne}:")
                code.append(f"    xor %rax, %rax")
                code.append(f"{lbl_done}:")
                code.append(f"    mov %rax, {träff_reg}  # träff = strcmp result")

        elif op == 'STORE_CHAR':
            char_var, idx_var, buf_name = stmt[1], stmt[2], stmt[3]
            named_buffers.add(buf_name)
            char_reg = resolve(char_var)
            if char_reg.startswith('$'):
                code.append(f"    mov {char_reg}, %rax")
                char_byte = '%al'
            else:
                byte_map = {
                    '%r12': '%r12b', '%r13': '%r13b', '%r8': '%r8b',
                    '%r9': '%r9b', '%r10': '%r10b', '%r11': '%r11b',
                    '%r15': '%r15b', '%r14': '%r14b',
                }
                char_byte = byte_map.get(char_reg, '%r15b')
            idx_reg = resolve(idx_var)
            code.append(f"    lea {buf_name}(%rip), %rsi")
            code.append(f"    mov {idx_reg}, %rcx")
            code.append(f"    add %rcx, %rsi")
            code.append(f"    mov {char_byte}, (%rsi)")

        elif op == 'SKRIV_BUF_NL':
            buf_name = stmt[1]
            named_buffers.add(buf_name)
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea {buf_name}(%rip), %rcx")
                code.append(f"    call puts")
                win_call_restore(to_save, align_pad)
            else:
                skriv_buf_used[0] = True
                lbl_start = new_label()
                lbl_end = new_label()
                code.append(f"    lea {buf_name}(%rip), %rsi")
                code.append(f"    xor %rdx, %rdx")
                code.append(f"{lbl_start}:")
                code.append(f"    cmpb $0, (%rsi,%rdx)")
                code.append(f"    je {lbl_end}")
                code.append(f"    inc %rdx")
                code.append(f"    jmp {lbl_start}")
                code.append(f"{lbl_end}:")
                code.append(f"    mov $1, %edi")
                code.append(f"    mov $1, %eax")
                code.append(f"    syscall")
                code.append(f"    lea _nl(%rip), %rsi")
                code.append(f"    mov $1, %rdx")
                code.append(f"    mov $1, %edi")
                code.append(f"    mov $1, %eax")
                code.append(f"    syscall")

        elif op == 'SKRIV_BUF':
            buf_name = stmt[1]
            named_buffers.add(buf_name)
            fmt_s_used[0] = True
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea fmt_s(%rip), %rcx")
                code.append(f"    lea {buf_name}(%rip), %rdx")
                code.append(f"    call printf")
                win_call_restore(to_save, align_pad)
            else:
                lbl_start = new_label()
                lbl_end = new_label()
                code.append(f"    lea {buf_name}(%rip), %rsi")
                code.append(f"    xor %rdx, %rdx")
                code.append(f"{lbl_start}:")
                code.append(f"    cmpb $0, (%rsi,%rdx)")
                code.append(f"    je {lbl_end}")
                code.append(f"    inc %rdx")
                code.append(f"    jmp {lbl_start}")
                code.append(f"{lbl_end}:")
                code.append(f"    mov $1, %edi")
                code.append(f"    mov $1, %eax")
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
        
        elif op == 'RETURN':
            # RETURN in IF/ELSE body - just store the value (don't exit function)
            ret_val = stmt[1]
            ret_reg = resolve(ret_val)
            code.append(f"    mov {ret_reg}, %r11  # _result (return)")
    
    has_exit = False
    for stmt in stmts:
        compile_stmt(stmt)
        if stmt[0] == 'EXIT':
            has_exit = True
    
    if not has_exit:
        if target == 'windows':
            code.append(f"    xorl %eax, %eax")
            code.append(f"    addq $32, %rsp")
            code.append(f"    popq %rbp")
            code.append(f"    ret")
        else:
            code.append(f"    mov $0, %edi")
            code.append(f"    mov $60, %rax")
            code.append(f"    syscall")

    data.append(".data")
    if target == 'windows':
        data.append('fmt_int: .asciz "%lld\\n"')
        if fmt_int_nonl_used[0]:
            data.append('fmt_int_nonl: .asciz "%lld"')
        if fmt_s_used[0]:
            data.append('fmt_s: .asciz "%s"')
    for i, s in enumerate(strings):
        escaped = s.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
        if target == 'windows':
            data.append(f"msg_{i}: .asciz \"{escaped}\"")
        else:
            data.append(f"msg_{i}: .ascii \"{escaped}\\n\\0\"")
    for i, s in enumerate(strings_nonl):
        escaped = s.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
        data.append(f"msg_nonl_{i}: .asciz \"{escaped}\"")
    for i, s in enumerate(lit_strings):
        escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        data.append(f'lit_{i}: .asciz "{escaped}"')
    data.append("num_buf: .byte 0")
    data.append("input_buf: .skip 256")
    for buf in sorted(named_buffers):
        data.append(f"{buf}: .skip 256")
    if target == 'linux' and skriv_buf_used[0]:
        data.append('_nl: .ascii "\\n"')
    data.append(".bss")
    data.append(".align 8")
    data.append("stack: .skip 4096")
    
    out = []
    out.append(".text")
    if target == 'windows':
        out.append(".globl main")
        out.append("main:")
        out.append("    pushq %rbp")
        out.append("    movq %rsp, %rbp")
        out.append("    subq $32, %rsp  # 32-byte shadow space (keeps 16-byte alignment)")
        out.append("    mov $65001, %ecx")
        out.append("    call SetConsoleOutputCP")
    else:
        out.append(".globl _start")
        out.append("_start:")
    out.append("    lea stack(%rip), %r14  # init stack ptr")
    out.extend(code)
    out.append("")
    out.extend(data)
    
    return '\n'.join(out)

def main():
    show_ord_lista = '--ord-lista' in sys.argv
    show_asm = '--asm' in sys.argv
    
    if len(sys.argv) < 2:
        print("Usage: python3 hiuh-native.py <input.hiuh> [output]")
        print("  --asm: Show assembly only")
        print("  --ord-lista: Show word list only")
        return
    
    if sys.argv[1] == '-' or sys.argv[1] == '--stdin':
        src = sys.stdin.buffer.read().decode('utf-8')
    elif sys.argv[1] == '--asm' or sys.argv[1] == '--ord-lista':
        src = open(sys.argv[2], encoding='utf-8').read()
    else:
        src = open(sys.argv[1], encoding='utf-8').read()
    
    result = tokenize(src)
    if isinstance(result, tuple):
        tokens, ord_lista = result
    else:
        tokens = result
        ord_lista = []
    use_windows = '--windows' in sys.argv or sys.platform == 'win32'
    target = 'windows' if use_windows else 'linux'

    stmts = parse(tokens)
    asm = compile_to_asm(stmts, target=target)

    if show_ord_lista:
        print(f"ORD_LISTA: {len(ord_lista)} ord")
        print(' '.join(ord_lista))
        return

    if show_asm:
        print(asm)
        return

    with tempfile.NamedTemporaryFile(mode='w', suffix='.s', delete=False, encoding='utf-8') as f:
        f.write(asm)
        asm_file = f.name

    if len(sys.argv) > 2 and not sys.argv[2].startswith('--'):
        output = sys.argv[2]
    else:
        base = os.path.splitext(os.path.basename(sys.argv[1]))[0]
        output = base + ('.exe' if use_windows else '')

    obj_file = asm_file + '.o'
    try:
        try:
            r = subprocess.run([CONFIG['as'], '-o', obj_file, asm_file], capture_output=True, text=True)
        except FileNotFoundError:
            print(f"Fel: Hittar inte assemblatorn '{CONFIG['as']}'.")
            print("Sätt rätt sökväg i hiuh.cfg under [tools] as = ...")
            return
        if r.returncode != 0:
            print(f"as error:\n{r.stderr}")
            return

        ld_cmd = [CONFIG['ld'], '-o', output, obj_file]
        if target == 'windows':
            ld_cmd += ['-lmingw32', '-lmsvcrt', '-lkernel32']
        try:
            r = subprocess.run(ld_cmd, capture_output=True, text=True)
        except FileNotFoundError:
            print(f"Fel: Hittar inte länkaren '{CONFIG['ld']}'.")
            print("Sätt rätt sökväg i hiuh.cfg under [tools] ld = ...")
            return
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