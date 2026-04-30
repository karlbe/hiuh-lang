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

def parse_condition(cond_words):
    """Parse a single condition like ['x', 'är', '0'] → ('EQ', 'x', '0')."""
    if 'mindre' in cond_words and 'än' in cond_words:
        return ('LT', cond_words[0], cond_words[cond_words.index('än') + 1])
    elif 'större' in cond_words and 'än' in cond_words:
        return ('GT', cond_words[0], cond_words[cond_words.index('än') + 1])
    elif 'är' in cond_words:
        är_i = cond_words.index('är')
        negated = är_i > 0 and cond_words[är_i - 1] == 'inte'
        after = cond_words[är_i + 1:]
        if after and after[0] == 'tom':
            var2 = 'texten '
        elif after and after[0] == 'texten':
            var2 = ' '.join(after) if len(after) > 1 else 'texten '
        else:
            var2 = after[0] if after else '0'
        return ('NE' if negated else 'EQ', cond_words[0], var2)
    return ('EQ', cond_words[0] if cond_words else '0', '0')


def tokenize(src):
    tokens = []
    ord_lista = []  # Word list for self-compilation
    
    for line in src.split('\n'):
        stripped = line.lstrip()
        if not stripped:
            continue
        words = stripped.split()
        first = words[0]
        # Strip inline comments: remove everything from a bare '.' word onward
        if first != '.':
            try:
                dot_i = words.index('.')
                words = words[:dot_i]
            except ValueError:
                pass

        # Save all non-comment words to ord_lista
        if first != '.':
            ord_lista.extend(words)
        
        if first in ('Skriv', 'SkrivNyRad'):
            # Preserve trailing spaces: extract raw content after keyword
            raw = line.rstrip('\n\r')
            rest = raw[raw.index(first) + len(first):].lstrip()
            # Strip inline comment from rest (bare ' . ' word)
            if ' . ' in rest:
                rest = rest[:rest.index(' . ')].rstrip()
            nl = first == 'SkrivNyRad'
            if rest.startswith('värdet av '):
                tokens.append(('SKRIV_VAR_NL' if nl else 'SKRIV_VAR', words[-1]))
            elif rest.startswith('text i '):
                tokens.append(('SKRIV_BUF_NL' if nl else 'SKRIV_BUF', rest[len('text i '):]))
            elif ' och ' in rest:
                parts = [p.strip() for p in rest.split(' och ')]
                tokens.append(('SKRIV_PARTS', nl, parts))
            else:
                tokens.append(('SKRIV_NL' if nl else 'SKRIV', rest))
        elif first == '.':
            # Comment line - skip
            continue
        elif first == 'Sätt' and len(words) >= 3:
            var = words[1]
            rest = ' '.join(words[3:]) if len(words) >= 4 else ''
            if rest == 'Läs':
                tokens.append(('READ_TO_VAR', var))
            elif rest.startswith('texten '):
                tokens.append(('SET_TEXT_LIT', var, rest[len('texten '):]))
            elif rest.lower().startswith('grej med '):
                # Inline lambda: Sätt foo till Grej med x, y
                params_str = rest[rest.lower().index('grej med ') + len('grej med '):]
                params = [p.strip() for p in params_str.split(',')]
                tokens.append(('GREJ_DEF', var, params))
            elif rest.startswith('Anropa '):
                # Real function call with result: Sätt x till Anropa foo med a, b
                rest2 = rest[len('Anropa '):]
                if ' med ' in rest2:
                    parts = rest2.split(' med ', 1)
                    func_name = parts[0].strip()
                    args = [a.strip() for a in parts[1].split(',')]
                else:
                    func_name = rest2.strip()
                    args = []
                tokens.append(('ANROPA_RES', var, func_name, args))
            elif rest.startswith('Jämför ') and ' med ' in rest:
                # Sätt x till Jämför buf med lit
                rw = rest.split()
                med_i = rw.index('med')
                buf = rw[1]
                lit = rw[med_i + 1] if med_i + 1 < len(rw) else ''
                if lit.startswith('"') and lit.endswith('"') and len(lit) >= 2:
                    lit = lit[1:-1]
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
            elif 'minus' in rest:
                parts = rest.split('minus')
                left = parts[0].strip()
                right = parts[1].strip() if len(parts) > 1 else '0'
                tokens.append(('MINUS', var, left, right))
            elif 'pluss' in rest:
                parts = rest.split('pluss')
                left = parts[0].strip()
                right = parts[1].strip() if len(parts) > 1 else '0'
                tokens.append(('PLUS', var, left, right))
            elif ' med ' in rest and not rest.lower().startswith('grej ') and not rest.startswith('Anropa '):
                # Inline function call: Sätt a till min med 2, 3
                parts = rest.split(' med ', 1)
                func_name = parts[0].strip()
                args = [a.strip() for a in parts[1].split(',')]
                tokens.append(('GREJ_CALL', var, func_name, args))
            elif rest.startswith('tecken ') and ' ur ' in rest:
                # CHAR_AT: Sätt tecken till tecken i ur källa
                parts = rest.split(' ur ')
                if len(parts) >= 2:
                    idx_part = parts[0].replace('tecken', '').strip()
                    source = parts[1].strip()
                    tokens.append(('SET_CHAR_AT', var, idx_part, source))
                else:
                    tokens.append(('SET', var, rest))
            elif ' är ' in rest and ' pluss ' not in rest and ' minus ' not in rest and ' med ' not in rest:
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
            if 'till' in words:
                till_i = words.index('till')
                var = words[till_i + 1] if till_i + 1 < len(words) else '_las_ok'
                tokens.append(('READ_TO_VAR', var))
            else:
                tokens.append(('READ',))

        elif first == 'LäsFil':
            # LäsFil text i filename_buf — read file into include buffer
            if 'i' in words:
                i_idx = words.index('i')
                buf = words[i_idx + 1] if i_idx + 1 < len(words) else 'input_buf'
                tokens.append(('LAS_FIL', buf))

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
                if lit.startswith('"') and lit.endswith('"') and len(lit) >= 2:
                    lit = lit[1:-1]
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

        elif first == 'Funktion':
            # Real function definition: Funktion foo med t är Text, n är Heltal
            name = words[1] if len(words) > 1 else ''
            if 'med' in words:
                med_i = words.index('med')
                args_str = ' '.join(words[med_i+1:])
                raw_params = [p.strip() for p in args_str.split(',') if p.strip()]
                params = []
                for rp in raw_params:
                    if ' är ' in rp:
                        pname, ptype = rp.split(' är ', 1)
                        params.append((pname.strip(), ptype.strip()))
                    else:
                        params.append((rp.strip(), 'Heltal'))
            else:
                params = []
            tokens.append(('FUNC_DEF', name, params))

        elif first == 'Anropa':
            # Real function call, discard result: Anropa foo med a, b
            if len(words) > 1:
                func_name = words[1]
                if 'med' in words:
                    med_i = words.index('med')
                    args_str = ' '.join(words[med_i+1:])
                    args = [a.strip() for a in args_str.split(',') if a.strip()]
                else:
                    args = []
                tokens.append(('ANROPA', func_name, args))

        elif first == 'Sålänge':
            rest = words[1:]
            if rest and 'är' in rest:
                var1 = rest[0]
                är_i = rest.index('är')
                if 'mindre' in rest and 'än' in rest:
                    cmp_type = 'LT'
                    var2 = rest[rest.index('än') + 1]
                elif 'större' in rest and 'än' in rest:
                    cmp_type = 'GT'
                    var2 = rest[rest.index('än') + 1]
                else:
                    negated = är_i > 0 and rest[är_i - 1] == 'inte'
                    after_är = rest[är_i + 1:]
                    if after_är and after_är[0] == 'tom':
                        var2 = 'texten '
                    elif after_är and after_är[0] == 'texten':
                        var2 = ' '.join(after_är) if len(after_är) > 1 else 'texten '
                    else:
                        var2 = after_är[0] if after_är else '0'
                    cmp_type = 'NE' if negated else 'EQ'
                tokens.append(('WHILE', cmp_type, var1, var2))

        elif first == 'KopieraBuffer':
            # KopieraBuffer src till dest
            if 'till' in words:
                till_i = words.index('till')
                src = words[1] if till_i > 1 else ''
                dest = words[till_i + 1] if till_i + 1 < len(words) else ''
                if src and dest:
                    tokens.append(('COPY_BUF', dest, src))

        elif first == 'Öka' and len(words) >= 2:
            var = words[1]
            tokens.append(('PLUS', var, var, '1'))

        elif first == 'Minska' and len(words) >= 2:
            var = words[1]
            tokens.append(('MINUS', var, var, '1'))

        elif first == 'Om':
            rest_str = ' '.join(words[1:])
            if ' och ' in rest_str:
                # Compound AND: "Om a är 0 och b är 1" → IF_AND [(EQ,a,0),(EQ,b,1)]
                conditions = [parse_condition(p.strip().split()) for p in rest_str.split(' och ')]
                tokens.append(('IF_AND', conditions))
            else:
                # Single condition
                rest = words[1:]
                if len(rest) >= 2:
                    var1 = rest[0]
                    if 'än' in words:
                        än_idx = words.index('än')
                        var2 = words[än_idx + 1] if än_idx + 1 < len(words) else rest[-1]
                        cmp_type = 'LT' if ('mindre' in words) else 'GT'
                    else:
                        är_i = words.index('är') if 'är' in words else -1
                        negated = är_i > 0 and words[är_i - 1] == 'inte'
                        after_är = words[är_i + 1:] if är_i >= 0 else []
                        if after_är and after_är[0] == 'tom':
                            var2 = 'texten '
                        elif after_är and after_är[0] == 'texten':
                            var2 = ' '.join(after_är) if len(after_är) > 1 else 'texten '
                        else:
                            var2 = rest[-1]
                        cmp_type = 'NE' if negated else 'EQ'
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
        
        elif 'är' in words and 'minus' in words:
            # "x är y minus z" → MINUS x y z
            var = first
            parts = words[words.index('är')+1:]
            minus_idx = parts.index('minus')
            left = ' '.join(parts[:minus_idx]).strip()
            right = ' '.join(parts[minus_idx+1:]).strip()
            tokens.append(('MINUS', var, left, right))

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
            if tok[0] == 'IF_AND':
                i += 1
                if_body, i = parse_block(i)
                blk.append(('IF_AND', tok[1], if_body))
            elif tok[0] == 'IF':
                if len(tok) >= 4:
                    cmp_type, v1, v2 = tok[1], tok[2], tok[3]
                    if cmp_type == 'LT':
                        blk.append(('CMP_LT', v1, v2))
                    elif cmp_type == 'GT':
                        blk.append(('CMP_GT', v1, v2))
                    elif cmp_type == 'NE':
                        blk.append(('CMP_NE', v1, v2))
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
            elif tok[0] == 'WHILE':
                i += 1
                inner, i = parse_block(i)
                blk.append(('WHILE', tok[1], tok[2], tok[3], inner))
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
        elif tok[0] == 'SKRIV_PARTS':
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
        elif tok[0] in ('PLUS', 'MINUS'):
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
        elif tok[0] == 'COPY_BUF':
            stmts.append(tok)
            i += 1
        elif tok[0] in ('SET_TEXT_LIT', 'READ_TO_VAR'):
            stmts.append(tok)
            i += 1
        elif tok[0] == 'READ_RES':
            stmts.append(tok)
            i += 1
        elif tok[0] == 'WHILE':
            i += 1
            body, i = parse_block(i)
            stmts.append(('WHILE', tok[1], tok[2], tok[3], body))
        elif tok[0] == 'FUNC_DEF':
            # Real function: parse body with parse_block
            i += 1
            body, i = parse_block(i)
            stmts.append(('REAL_FUNC', tok[1], tok[2], body))
        elif tok[0] == 'GREJ_DEF':
            # Inline lambda: parse function body until END, handling nested IF-ELSE
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
            stmts.append(('GREJ', tok[1], tok[2], body))
        elif tok[0] in ('GREJ_CALL', 'ANROPA', 'ANROPA_RES'):
            stmts.append(tok)
            i += 1
        elif tok[0] == 'IF_AND':
            body = []
            i += 1
            while i < len(tokens) and tokens[i][0] not in ('END', 'ELSE'):
                body.append(tokens[i])
                i += 1
            if i < len(tokens) and tokens[i][0] == 'END':
                i += 1
            stmts.append(('IF_AND', tok[1], body))

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
                elif cmp_type == 'NE':
                    stmts.append(('CMP_NE', var1, var2))
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
        
        elif tok[0] in ('CMP', 'CMP_NE', 'CMP_LT', 'CMP_GT'):
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
    grej_defs = {}
    next_reg = [0]
    pending_real_funcs = []
    in_real_func = [False]
    func_returned = [False]
    reg_names = ['%r12', '%r13', '%r8', '%r9', '%r10', '%r11', '%rbp']  # 7 vars max
    # Track reserved registers
    reserved = {'%r14': 'stack pointer', '%r15': 'temp/char result'}
    labels = [0]
    loop_labels = []  # stack of loop_end labels for Bryt (break)
    named_buffers = set()
    var_types = {}        # varname -> 'Heltal' | 'Text'
    text_bufs = {}        # varname -> buffer label (_text_N)
    next_text_buf = [0]
    skriv_buf_used = [False]
    fmt_s_used = [False]       # "%s" format string for no-newline printf
    fmt_int_nonl_used = [False]  # "%lld" format string (no newline)
    lit_strings = []
    strings_nonl = []  # strings for SKRIV (no newline)

    def alloc_var(v):
        if v not in var_reg:
            reg = reg_names[next_reg[0] % len(reg_names)]
            while reg in reserved:
                next_reg[0] += 1
                reg = reg_names[next_reg[0] % len(reg_names)]
            var_reg[v] = reg
            next_reg[0] += 1
        return var_reg[v]

    def alloc_text_var(v):
        if v in var_types and var_types[v] == 'Heltal':
            raise RuntimeError(f"Typfel: kan inte tilldela Text till Heltal-variabel '{v}'")
        if v not in text_bufs:
            text_bufs[v] = f'_text_{next_text_buf[0]}'
            next_text_buf[0] += 1
        var_types[v] = 'Text'
        return text_bufs[v]

    def is_text(v):
        return var_types.get(v) in ('Text', 'TextPtr')

    def load_text_addr(v, reg):
        """Emit code to load the address of v's text buffer into reg."""
        t = var_types.get(v)
        if t == 'Text':
            code.append(f"    lea {text_bufs[v]}(%rip), {reg}")
        elif t == 'TextPtr':
            code.append(f"    mov {var_reg[v]}, {reg}")

    def emit_strcpy(dest_var_or_buf, src_var_or_buf):
        """Copy text. Args may be variable names (looked up) or raw buffer labels."""
        if target == 'windows':
            to_save, align_pad = win_call_save()
            if dest_var_or_buf in var_types:
                load_text_addr(dest_var_or_buf, '%rcx')
            else:
                code.append(f"    lea {dest_var_or_buf}(%rip), %rcx")
            if src_var_or_buf in var_types:
                load_text_addr(src_var_or_buf, '%rdx')
            else:
                code.append(f"    lea {src_var_or_buf}(%rip), %rdx")
            code.append(f"    call strcpy")
            win_call_restore(to_save, align_pad)
        else:
            lbl_loop = new_label()
            lbl_done = new_label()
            if dest_var_or_buf in var_types:
                load_text_addr(dest_var_or_buf, '%rdi')
            else:
                code.append(f"    lea {dest_var_or_buf}(%rip), %rdi")
            if src_var_or_buf in var_types:
                load_text_addr(src_var_or_buf, '%rsi')
            else:
                code.append(f"    lea {src_var_or_buf}(%rip), %rsi")
            code.append(f"{lbl_loop}:")
            code.append(f"    movb (%rsi), %al")
            code.append(f"    movb %al, (%rdi)")
            code.append(f"    testb %al, %al")
            code.append(f"    jz {lbl_done}")
            code.append(f"    inc %rsi")
            code.append(f"    inc %rdi")
            code.append(f"    jmp {lbl_loop}")
            code.append(f"{lbl_done}:")
    
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

    def emit_incl_buf_read(lbl_copy, lbl_cr, lbl_nl, lbl_eof, lbl_after):
        """Emit code that copies one line from _hiuh_incl_buf[pos] to input_buf.
        Strips \\r\\n, null-terminates, advances _hiuh_incl_pos.
        %rax must hold _hiuh_incl_pos value on entry. Falls through to lbl_after."""
        code.append(f"    lea _hiuh_incl_buf(%rip), %rsi")
        code.append(f"    add %rax, %rsi  # rsi = &incl_buf[pos]")
        code.append(f"    lea input_buf(%rip), %rdi")
        code.append(f"{lbl_copy}:")
        code.append(f"    movb (%rsi), %al")
        code.append(f"    cmpb $13, %al")
        code.append(f"    je {lbl_cr}")
        code.append(f"    cmpb $10, %al")
        code.append(f"    je {lbl_nl}")
        code.append(f"    testb %al, %al")
        code.append(f"    jz {lbl_eof}")
        code.append(f"    movb %al, (%rdi)")
        code.append(f"    inc %rsi")
        code.append(f"    inc %rdi")
        code.append(f"    jmp {lbl_copy}")
        code.append(f"{lbl_cr}:")
        code.append(f"    inc %rsi")
        code.append(f"    jmp {lbl_copy}")
        code.append(f"{lbl_nl}:")
        code.append(f"    inc %rsi  # skip \\n")
        code.append(f"{lbl_eof}:")
        code.append(f"    movb $0, (%rdi)")
        code.append(f"    lea _hiuh_incl_buf(%rip), %rcx")
        code.append(f"    sub %rcx, %rsi  # new pos = rsi - buf start")
        code.append(f"    mov %rsi, _hiuh_incl_pos(%rip)")
        code.append(f"    jmp {lbl_after}")

    def hiuh_call_save(exclude=None):
        cs = {'%r8', '%r9', '%r10', '%r11'}
        to_save = sorted(r for r in var_reg.values() if r in cs and r != exclude)
        align_pad = 8 if len(to_save) % 2 == 1 else 0
        if align_pad:
            code.append(f"    subq $8, %rsp")
        for reg in to_save:
            code.append(f"    push {reg}")
        if target == 'windows':
            code.append(f"    subq $32, %rsp  # shadow space")
        return to_save, align_pad

    def hiuh_call_restore(to_save, align_pad):
        if target == 'windows':
            code.append(f"    addq $32, %rsp")
        for reg in reversed(to_save):
            code.append(f"    pop {reg}")
        if align_pad:
            code.append(f"    addq $8, %rsp")

    def emit_func_epilogue():
        if target == 'windows':
            code.append(f"    addq $32, %rsp")
        code.append(f"    pop %rbp")
        code.append(f"    pop %r13")
        code.append(f"    pop %r12")
        code.append(f"    ret")

    def compile_real_func(name, params, body):
        saved_var_reg = dict(var_reg)
        saved_next_reg = next_reg[0]
        saved_loop_labels = list(loop_labels)
        saved_var_types = dict(var_types)
        var_reg.clear()
        next_reg[0] = 0
        loop_labels.clear()
        var_types.clear()
        in_real_func[0] = True

        code.append(f"{name}:")
        code.append(f"    push %r12")
        code.append(f"    push %r13")
        code.append(f"    push %rbp")
        if target == 'windows':
            code.append(f"    subq $32, %rsp  # shadow space")

        arg_regs = ['%rcx', '%rdx', '%r8', '%r9'] if target == 'windows' else ['%rdi', '%rsi', '%rdx', '%rcx']
        for j, param_info in enumerate(params[:4]):
            if isinstance(param_info, tuple):
                param, ptype = param_info
            else:
                param, ptype = param_info, 'Heltal'
            reg = alloc_var(param)
            code.append(f"    mov {arg_regs[j]}, {reg}  # param {param}")
            var_types[param] = 'TextPtr' if ptype == 'Text' else 'Heltal'

        func_returned[0] = False
        for s in body:
            compile_stmt(s)

        if not func_returned[0]:
            code.append(f"    xor %eax, %eax")
            emit_func_epilogue()
        func_returned[0] = False

        in_real_func[0] = False
        var_reg.clear()
        var_reg.update(saved_var_reg)
        next_reg[0] = saved_next_reg
        loop_labels.clear()
        loop_labels.extend(saved_loop_labels)
        var_types.clear()
        var_types.update(saved_var_types)

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
            varname = stmt[1]
            if is_text(varname):
                if target == 'windows':
                    to_save, align_pad = win_call_save()
                    load_text_addr(varname, '%rcx')
                    code.append(f"    call puts")
                    win_call_restore(to_save, align_pad)
                else:
                    skriv_buf_used[0] = True
                    lbl_start = new_label()
                    lbl_end = new_label()
                    load_text_addr(varname, '%rsi')
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
            else:
                reg = resolve(varname)
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
            varname = stmt[1]
            if is_text(varname):
                fmt_s_used[0] = True
                if target == 'windows':
                    to_save, align_pad = win_call_save()
                    code.append(f"    lea fmt_s(%rip), %rcx")
                    load_text_addr(varname, '%rdx')
                    code.append(f"    call printf")
                    win_call_restore(to_save, align_pad)
                else:
                    lbl_start = new_label()
                    lbl_end = new_label()
                    load_text_addr(varname, '%rsi')
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
            else:
                reg = resolve(varname)
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
                        code.append(f"    mov {reg}, %rax  # print {varname}")
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
        
        elif op == 'SKRIV_PARTS':
            nl = stmt[1]
            parts = stmt[2]
            for j, part in enumerate(parts):
                is_last = (j == len(parts) - 1)
                if part.startswith('text i '):
                    buf = part[len('text i '):]
                    if is_last and nl:
                        compile_stmt(('SKRIV_BUF_NL', buf))
                    else:
                        compile_stmt(('SKRIV_BUF', buf))
                elif part in var_reg or part in var_types:
                    if is_last and nl:
                        compile_stmt(('SKRIV_VAR_NL', part))
                    else:
                        compile_stmt(('SKRIV_VAR', part))
                else:
                    if is_last and nl:
                        compile_stmt(('SKRIV_NL', part))
                    else:
                        compile_stmt(('SKRIV', part))

        elif op == 'SET':
            var = stmt[1]
            val = stmt[2]
            if is_text(val):
                if var in var_types and var_types[var] == 'Heltal':
                    raise RuntimeError(f"Typfel: kan inte tilldela Text till Heltal-variabel '{var}'")
                alloc_text_var(var)
                emit_strcpy(var, val)
            else:
                if var in var_types and var_types[var] == 'Text':
                    raise RuntimeError(f"Typfel: kan inte tilldela Heltal till Text-variabel '{var}'")
                var_types[var] = 'Heltal'
                reg = alloc_var(var)
                r = resolve(val)
                code.append(f"    mov {r}, {reg}  # {var} = {val}")
        
        elif op == 'SET_TEXT_LIT':
            var, lit = stmt[1], stmt[2]
            alloc_text_var(var)
            lit_strings.append(lit)
            lit_idx = len(lit_strings) - 1
            emit_strcpy(var, f'lit_{lit_idx}')

        elif op == 'READ_TO_VAR':
            var = stmt[1]
            buf = alloc_text_var(var)
            lbl_have_data  = new_label()
            lbl_copy       = new_label()
            lbl_cr         = new_label()
            lbl_nl         = new_label()
            lbl_copy_eof   = new_label()
            lbl_strip      = new_label()
            lbl_strip_null = new_label()
            lbl_strip_done = new_label()
            lbl_done       = new_label()
            lbl_eof_null   = new_label()
            lbl_blank_line = new_label()
            lbl_after_copy = new_label()
            # Read into input_buf (same as READ) so char indexing still works,
            # then copy to the text variable buffer for string comparison.
            # Blank lines (fgets non-NULL but content empty after strip) store '\n'
            # in the text buffer so Sålänge X inte är tom continues past blank lines.
            # EOF (fgets NULL) leaves the text buffer empty, so the while exits.
            # Check include buffer first
            code.append(f"    mov _hiuh_incl_pos(%rip), %rax")
            code.append(f"    cmp _hiuh_incl_end(%rip), %rax")
            code.append(f"    jl {lbl_have_data}")
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea input_buf(%rip), %rax")
                code.append(f"    movb $0, (%rax)  # pre-zero: 0 on EOF")
                code.append(f"    mov $0, %ecx")
                code.append(f"    call __acrt_iob_func")
                code.append(f"    mov %rax, %r8")
                code.append(f"    lea input_buf(%rip), %rcx")
                code.append(f"    mov $256, %edx")
                code.append(f"    call fgets")
                win_call_restore(to_save, align_pad)
                # %rax = fgets return (NULL=EOF, else=got data). Check BEFORE strip
                # clobbers %al.
                code.append(f"    test %rax, %rax")
                code.append(f"    jz {lbl_eof_null}  # NULL = EOF, leave buf empty")
            else:
                code.append(f"    lea input_buf(%rip), %rax")
                code.append(f"    movb $0, (%rax)")
                code.append(f"    mov $0, %eax")
                code.append(f"    mov $0, %edi")
                code.append(f"    lea input_buf(%rip), %rsi")
                code.append(f"    mov $256, %edx")
                code.append(f"    syscall")
                code.append(f"    test %rax, %rax")
                code.append(f"    jz {lbl_eof_null}  # 0 bytes = EOF")
            # strip trailing \n / \r from input_buf
            code.append(f"    lea input_buf(%rip), %rsi")
            code.append(f"{lbl_strip}:")
            code.append(f"    movb (%rsi), %al")
            code.append(f"    testb %al, %al")
            code.append(f"    jz {lbl_strip_done}")
            code.append(f"    cmpb $10, %al")
            code.append(f"    je {lbl_strip_null}")
            code.append(f"    cmpb $13, %al")
            code.append(f"    je {lbl_strip_null}")
            code.append(f"    inc %rsi")
            code.append(f"    jmp {lbl_strip}")
            code.append(f"{lbl_strip_null}:")
            code.append(f"    movb $0, (%rsi)")
            code.append(f"{lbl_strip_done}:")
            # After stripping: if input_buf is now empty it was a blank line.
            # Store '\n' in the text buffer so the Sålänge loop continues.
            code.append(f"    movb input_buf(%rip), %al")
            code.append(f"    testb %al, %al")
            code.append(f"    jz {lbl_blank_line}")
            code.append(f"    jmp {lbl_done}")
            code.append(f"{lbl_eof_null}:")
            code.append(f"    jmp {lbl_done}  # EOF: buf stays empty")
            # Include buffer path
            code.append(f"{lbl_have_data}:")
            emit_incl_buf_read(lbl_copy, lbl_cr, lbl_nl, lbl_copy_eof, lbl_done)
            code.append(f"{lbl_done}:")
            # copy input_buf -> text variable so while/if conditions can compare it
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea {buf}(%rip), %rcx")
                code.append(f"    lea input_buf(%rip), %rdx")
                code.append(f"    call strcpy")
                win_call_restore(to_save, align_pad)
            else:
                code.append(f"    lea {buf}(%rip), %rdi")
                code.append(f"    lea input_buf(%rip), %rsi")
                code.append(f"    call strcpy")
            code.append(f"    jmp {lbl_after_copy}")
            code.append(f"{lbl_blank_line}:")
            # Blank line: write '\n' (10) + '\0' to text buf so while continues
            code.append(f"    lea {buf}(%rip), %rdi")
            code.append(f"    movb $10, (%rdi)")
            code.append(f"    movb $0, 1(%rdi)")
            code.append(f"{lbl_after_copy}:")

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

        elif op == 'MINUS':
            var = stmt[1]
            left = stmt[2]
            right = stmt[3]
            reg = alloc_var(var)
            r1 = resolve(left)
            r2 = resolve(right)
            code.append(f"    mov {r1}, %rcx  # {var} = {left} - {right}")
            code.append(f"    sub {r2}, %rcx")
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
                
        elif op == 'IF_AND':
            conditions, body = stmt[1], stmt[2]
            if_end = new_label()
            for (cmp_type, var1, var2) in conditions:
                if cmp_type == 'LT':
                    compile_stmt(('CMP_LT', var1, var2))
                elif cmp_type == 'GT':
                    compile_stmt(('CMP_GT', var1, var2))
                else:
                    compile_stmt(('CMP', var1, var2))
                code.append(f"    test %al, %al")
                code.append(f"    jz {if_end}")
            for s in body:
                compile_stmt(s)
            code.append(f"{if_end}:")

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
        
        elif op == 'GREJ':
            grej_defs[stmt[1]] = stmt

        elif op == 'GREJ_CALL':
            var, func_name, args = stmt[1], stmt[2], stmt[3]
            if func_name in grej_defs:
                grej = grej_defs[func_name]
                params = grej[2]
                body = grej[3]
                for p, a in zip(params, args):
                    compile_stmt(('SET', p, a))
                for s in body:
                    if s[0] == 'RETURN':
                        ret_reg = resolve(s[1])
                        code.append(f"    mov {ret_reg}, %r11  # _result")
                        break
                    compile_stmt(s)
            reg = alloc_var(var)
            code.append(f"    mov %r11, {reg}  # {var} = _result")

        elif op == 'REAL_FUNC':
            pending_real_funcs.append(stmt)

        elif op == 'ANROPA':
            func_name, args = stmt[1], stmt[2]
            to_save, align_pad = hiuh_call_save()
            arg_regs = ['%rcx', '%rdx', '%r8', '%r9'] if target == 'windows' else ['%rdi', '%rsi', '%rdx', '%rcx']
            for j, arg in enumerate(args[:4]):
                if is_text(arg):
                    load_text_addr(arg, arg_regs[j])
                else:
                    code.append(f"    mov {resolve(arg)}, {arg_regs[j]}")
            code.append(f"    call {func_name}")
            hiuh_call_restore(to_save, align_pad)

        elif op == 'ANROPA_RES':
            var, func_name, args = stmt[1], stmt[2], stmt[3]
            res_reg = alloc_var(var)
            to_save, align_pad = hiuh_call_save(exclude=res_reg)
            arg_regs = ['%rcx', '%rdx', '%r8', '%r9'] if target == 'windows' else ['%rdi', '%rsi', '%rdx', '%rcx']
            for j, arg in enumerate(args[:4]):
                if is_text(arg):
                    load_text_addr(arg, arg_regs[j])
                else:
                    code.append(f"    mov {resolve(arg)}, {arg_regs[j]}")
            code.append(f"    call {func_name}")
            hiuh_call_restore(to_save, align_pad)
            code.append(f"    mov %rax, {res_reg}  # {var} = result")
        
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
            # Inline text literal: "t är texten hej" — var2 is a text literal phrase
            if var2.startswith('texten '):
                lit = var2[len('texten '):]
                lit_strings.append(lit)
                lit_idx = len(lit_strings) - 1
                if target == 'windows':
                    to_save, align_pad = win_call_save()
                    load_text_addr(var1, '%rcx') if is_text(var1) else code.append(f"    mov {resolve(var1)}, %rcx")
                    code.append(f"    lea lit_{lit_idx}(%rip), %rdx")
                    code.append(f"    call strcmp")
                    code.append(f"    test %eax, %eax")
                    code.append(f"    sete %al")
                    win_call_restore(to_save, align_pad)
                else:
                    lbl_loop = new_label(); lbl_ne = new_label(); lbl_eq = new_label(); lbl_done = new_label()
                    load_text_addr(var1, '%rsi') if is_text(var1) else code.append(f"    mov {resolve(var1)}, %rsi")
                    code.append(f"    lea lit_{lit_idx}(%rip), %rdi")
                    code.append(f"{lbl_loop}:")
                    code.append(f"    movb (%rsi), %al"); code.append(f"    movb (%rdi), %cl")
                    code.append(f"    cmpb %cl, %al"); code.append(f"    jne {lbl_ne}")
                    code.append(f"    testb %al, %al"); code.append(f"    jz {lbl_eq}")
                    code.append(f"    inc %rsi"); code.append(f"    inc %rdi"); code.append(f"    jmp {lbl_loop}")
                    code.append(f"{lbl_eq}:"); code.append(f"    mov $1, %rax"); code.append(f"    jmp {lbl_done}")
                    code.append(f"{lbl_ne}:"); code.append(f"    xor %rax, %rax")
                    code.append(f"{lbl_done}:"); code.append(f"    test %rax, %rax"); code.append(f"    setne %al")
            elif is_text(var1) or is_text(var2):
                if target == 'windows':
                    to_save, align_pad = win_call_save()
                    load_text_addr(var1, '%rcx') if is_text(var1) else code.append(f"    mov {resolve(var1)}, %rcx")
                    load_text_addr(var2, '%rdx') if is_text(var2) else code.append(f"    mov {resolve(var2)}, %rdx")
                    code.append(f"    call strcmp")
                    code.append(f"    test %eax, %eax")
                    code.append(f"    sete %al")
                    win_call_restore(to_save, align_pad)
                else:
                    lbl_loop = new_label()
                    lbl_ne = new_label()
                    lbl_eq = new_label()
                    lbl_done = new_label()
                    load_text_addr(var1, '%rsi') if is_text(var1) else code.append(f"    mov {resolve(var1)}, %rsi")
                    load_text_addr(var2, '%rdi') if is_text(var2) else code.append(f"    mov {resolve(var2)}, %rdi")
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
                    code.append(f"    test %rax, %rax")
                    code.append(f"    setne %al")
            else:
                r1 = var_reg.get(var1, '%r12')
                try:
                    val2 = int(var2)
                    code.append(f"    mov {r1}, %rax  # cmp {var1} == {var2}")
                    code.append(f"    cmp ${val2}, %rax")
                except ValueError:
                    r2 = var_reg.get(var2, '%r12')
                    code.append(f"    mov {r2}, %rax  # cmp {var1} == {var2}")
                    code.append(f"    cmp {r1}, %rax")
                code.append(f"    sete %al")
        
        elif op == 'CMP_NE':
            compile_stmt(('CMP', stmt[1], stmt[2]))
            code.append(f"    xor $1, %al  # negate: NE")

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
        
        elif op == 'READ_RES':
            res_reg = alloc_var(stmt[1])
            lbl_have_data  = new_label()
            lbl_copy       = new_label()
            lbl_cr         = new_label()
            lbl_nl         = new_label()
            lbl_copy_eof   = new_label()
            lbl_strip      = new_label()
            lbl_strip_null = new_label()
            lbl_strip_done = new_label()
            lbl_done       = new_label()
            # Check include buffer first
            code.append(f"    mov _hiuh_incl_pos(%rip), %rax")
            code.append(f"    cmp _hiuh_incl_end(%rip), %rax")
            code.append(f"    jl {lbl_have_data}")
            if target == 'windows':
                to_save, align_pad = win_call_save(exclude=res_reg)
                code.append(f"    lea input_buf(%rip), %rax")
                code.append(f"    movb $0, (%rax)  # pre-zero")
                code.append(f"    mov $0, %ecx")
                code.append(f"    call __acrt_iob_func  # get stdin FILE*")
                code.append(f"    mov %rax, %r8")
                code.append(f"    lea input_buf(%rip), %rcx")
                code.append(f"    mov $256, %edx")
                code.append(f"    call fgets")
                code.append(f"    test %rax, %rax")
                code.append(f"    setne %al")
                code.append(f"    movzx %al, %rax")
                win_call_restore(to_save, align_pad)
                code.append(f"    mov %rax, {res_reg}  # {stmt[1]} = 1 if ok, 0 if EOF")
            else:
                code.append(f"    lea input_buf(%rip), %rax")
                code.append(f"    movb $0, (%rax)  # pre-zero")
                code.append(f"    mov $0, %eax  # read")
                code.append(f"    mov $0, %edi  # stdin")
                code.append(f"    lea input_buf(%rip), %rsi")
                code.append(f"    mov $256, %edx  # max bytes")
                code.append(f"    syscall")
                code.append(f"    test %rax, %rax")
                code.append(f"    setg %al")
                code.append(f"    movzx %al, %rax")
                code.append(f"    mov %rax, {res_reg}  # {stmt[1]} = 1 if ok, 0 if EOF")
            # strip trailing \n / \r from input_buf
            code.append(f"    lea input_buf(%rip), %rsi")
            code.append(f"{lbl_strip}:")
            code.append(f"    movb (%rsi), %al")
            code.append(f"    testb %al, %al")
            code.append(f"    jz {lbl_strip_done}")
            code.append(f"    cmpb $10, %al")
            code.append(f"    je {lbl_strip_null}")
            code.append(f"    cmpb $13, %al")
            code.append(f"    je {lbl_strip_null}")
            code.append(f"    inc %rsi")
            code.append(f"    jmp {lbl_strip}")
            code.append(f"{lbl_strip_null}:")
            code.append(f"    movb $0, (%rsi)")
            code.append(f"{lbl_strip_done}:")
            code.append(f"    jmp {lbl_done}")
            # Include buffer path: read line, then set result=1
            lbl_incl_after = new_label()
            code.append(f"{lbl_have_data}:")
            emit_incl_buf_read(lbl_copy, lbl_cr, lbl_nl, lbl_copy_eof, lbl_incl_after)
            code.append(f"{lbl_incl_after}:")
            code.append(f"    mov $1, {res_reg}  # got data from include buffer")
            code.append(f"{lbl_done}:")

        elif op == 'LAS_FIL':
            # LäsFil text i buf — open file, fread into _hiuh_incl_buf
            buf = stmt[1]
            if buf not in ('input_buf', 'ord_buf'):
                named_buffers.add(buf)
            lbl_fil_done = new_label()
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea {buf}(%rip), %rcx")
                code.append(f"    lea _hiuh_incl_mode(%rip), %rdx")
                code.append(f"    call fopen")
                code.append(f"    test %rax, %rax")
                code.append(f"    jz {lbl_fil_done}")
                code.append(f"    mov %rax, _hiuh_incl_fp(%rip)")
                code.append(f"    lea _hiuh_incl_buf(%rip), %rcx")
                code.append(f"    mov $1, %edx")
                code.append(f"    mov $65536, %r8d")
                code.append(f"    mov _hiuh_incl_fp(%rip), %r9")
                code.append(f"    call fread")
                code.append(f"    mov %rax, _hiuh_incl_end(%rip)")
                code.append(f"    movq $0, _hiuh_incl_pos(%rip)")
                code.append(f"    mov _hiuh_incl_fp(%rip), %rcx")
                code.append(f"    call fclose")
                code.append(f"{lbl_fil_done}:")
                win_call_restore(to_save, align_pad)

        elif op == 'WHILE':
            cmp_type, var1, var2, body = stmt[1], stmt[2], stmt[3], stmt[4]
            loop_start = new_label()
            loop_end = new_label()
            if cmp_type in ('EQ', 'NE') and isinstance(var2, str) and var2.startswith('texten '):
                lit = var2[len('texten '):]
                lit_strings.append(lit)
                lit_idx = len(lit_strings) - 1
                code.append(f"{loop_start}:  # Sålänge texten")
                if target == 'windows':
                    to_save, align_pad = win_call_save()
                    load_text_addr(var1, '%rcx') if is_text(var1) else code.append(f"    mov {resolve(var1)}, %rcx")
                    code.append(f"    lea lit_{lit_idx}(%rip), %rdx")
                    code.append(f"    call strcmp")
                    win_call_restore(to_save, align_pad)
                else:
                    lbl_loop = new_label(); lbl_ne = new_label(); lbl_eq = new_label(); lbl_done = new_label()
                    load_text_addr(var1, '%rsi') if is_text(var1) else code.append(f"    mov {resolve(var1)}, %rsi")
                    code.append(f"    lea lit_{lit_idx}(%rip), %rdi")
                    code.append(f"{lbl_loop}:")
                    code.append(f"    movb (%rsi), %al"); code.append(f"    movb (%rdi), %cl")
                    code.append(f"    cmpb %cl, %al"); code.append(f"    jne {lbl_ne}")
                    code.append(f"    testb %al, %al"); code.append(f"    jz {lbl_eq}")
                    code.append(f"    inc %rsi"); code.append(f"    inc %rdi"); code.append(f"    jmp {lbl_loop}")
                    code.append(f"{lbl_eq}:"); code.append(f"    xor %eax, %eax"); code.append(f"    jmp {lbl_done}")
                    code.append(f"{lbl_ne}:"); code.append(f"    mov $1, %eax")
                    code.append(f"{lbl_done}:")
                code.append(f"    test %eax, %eax")
                # EQ: loop while equal (exit when not equal); NE: loop while not equal (exit when equal)
                code.append(f"    {'jne' if cmp_type == 'EQ' else 'je'} {loop_end}")
            else:
                r1 = resolve(var1)
                r2 = resolve(var2)
                code.append(f"{loop_start}:  # Sålänge")
                code.append(f"    mov {r1}, %rax")
                code.append(f"    cmp {r2}, %rax")
                if cmp_type == 'EQ':
                    code.append(f"    jne {loop_end}")
                elif cmp_type == 'NE':
                    code.append(f"    je {loop_end}")
                elif cmp_type == 'LT':
                    code.append(f"    jge {loop_end}")
                elif cmp_type == 'GT':
                    code.append(f"    jle {loop_end}")
            loop_labels.append(loop_end)
            for s in body:
                compile_stmt(s)
            loop_labels.pop()
            code.append(f"    jmp {loop_start}")
            code.append(f"{loop_end}:")

        elif op == 'READ':
            lbl_have_data  = new_label()
            lbl_copy       = new_label()
            lbl_cr         = new_label()
            lbl_nl         = new_label()
            lbl_copy_eof   = new_label()
            lbl_strip      = new_label()
            lbl_strip_null = new_label()
            lbl_strip_done = new_label()
            lbl_done       = new_label()
            # Check include buffer first
            code.append(f"    mov _hiuh_incl_pos(%rip), %rax")
            code.append(f"    cmp _hiuh_incl_end(%rip), %rax")
            code.append(f"    jl {lbl_have_data}")
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea input_buf(%rip), %rax")
                code.append(f"    movb $0, (%rax)  # pre-zero: 0 on EOF after fgets")
                code.append(f"    mov $0, %ecx")
                code.append(f"    call __acrt_iob_func  # get stdin FILE*")
                code.append(f"    mov %rax, %r8")
                code.append(f"    lea input_buf(%rip), %rcx")
                code.append(f"    mov $256, %edx")
                code.append(f"    call fgets")
                win_call_restore(to_save, align_pad)
            else:
                code.append(f"    lea input_buf(%rip), %rax")
                code.append(f"    movb $0, (%rax)  # pre-zero: 0 on EOF after read")
                code.append(f"    mov $0, %eax  # read")
                code.append(f"    mov $0, %edi  # stdin")
                code.append(f"    lea input_buf(%rip), %rsi")
                code.append(f"    mov $256, %edx  # max bytes")
                code.append(f"    syscall")
            # strip trailing \n / \r from input_buf
            code.append(f"    lea input_buf(%rip), %rsi")
            code.append(f"{lbl_strip}:")
            code.append(f"    movb (%rsi), %al")
            code.append(f"    testb %al, %al")
            code.append(f"    jz {lbl_strip_done}")
            code.append(f"    cmpb $10, %al")
            code.append(f"    je {lbl_strip_null}")
            code.append(f"    cmpb $13, %al")
            code.append(f"    je {lbl_strip_null}")
            code.append(f"    inc %rsi")
            code.append(f"    jmp {lbl_strip}")
            code.append(f"{lbl_strip_null}:")
            code.append(f"    movb $0, (%rsi)")
            code.append(f"{lbl_strip_done}:")
            code.append(f"    jmp {lbl_done}")
            # Include buffer path (jumped to from check above)
            code.append(f"{lbl_have_data}:")
            emit_incl_buf_read(lbl_copy, lbl_cr, lbl_nl, lbl_copy_eof, lbl_done)
            code.append(f"{lbl_done}:")
        
        elif op == 'CMP_BUF_LIT':
            target_var, buf_name, literal = stmt[1], stmt[2], stmt[3]
            if buf_name != 'input_buf':
                named_buffers.add(buf_name)
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
                    '%r15': '%r15b', '%r14': '%r14b', '%rbp': '%bpl',
                }
                char_byte = byte_map.get(char_reg, '%r15b')
            idx_reg = resolve(idx_var)
            code.append(f"    lea {buf_name}(%rip), %rsi")
            code.append(f"    mov {idx_reg}, %rcx")
            code.append(f"    add %rcx, %rsi")
            code.append(f"    mov {char_byte}, (%rsi)")

        elif op == 'COPY_BUF':
            dest, src = stmt[1], stmt[2]
            if dest != 'input_buf':
                named_buffers.add(dest)
            if src != 'input_buf':
                named_buffers.add(src)
            if target == 'windows':
                to_save, align_pad = win_call_save()
                code.append(f"    lea {dest}(%rip), %rcx")
                code.append(f"    lea {src}(%rip), %rdx")
                code.append(f"    call strcpy")
                win_call_restore(to_save, align_pad)
            else:
                lbl_loop = new_label()
                lbl_done = new_label()
                code.append(f"    lea {dest}(%rip), %rdi")
                code.append(f"    lea {src}(%rip), %rsi")
                code.append(f"{lbl_loop}:")
                code.append(f"    movb (%rsi), %al")
                code.append(f"    movb %al, (%rdi)")
                code.append(f"    testb %al, %al")
                code.append(f"    jz {lbl_done}")
                code.append(f"    inc %rsi")
                code.append(f"    inc %rdi")
                code.append(f"    jmp {lbl_loop}")
                code.append(f"{lbl_done}:")

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
            idx, src_buf = stmt[1], stmt[2]
            buf = src_buf if src_buf else 'input_buf'
            if buf != 'input_buf':
                named_buffers.add(buf)
            if idx in var_reg:
                code.append(f"    mov {var_reg[idx]}, %rcx  # index")
            else:
                try:
                    code.append(f"    mov ${int(idx)}, %rcx  # index")
                except:
                    code.append(f"    mov $0, %rcx  # index fallback")
            code.append(f"    lea {buf}(%rip), %rsi")
            code.append(f"    add %rcx, %rsi")
            code.append(f"    mov (%rsi), %r15b  # character at index")
            var_reg['_tecken'] = '%r15'
            var_reg['tecken'] = '%r15'
        
        elif op == 'RETURN':
            ret_reg = resolve(stmt[1])
            if in_real_func[0]:
                code.append(f"    mov {ret_reg}, %rax  # return value")
                emit_func_epilogue()
                func_returned[0] = True
            else:
                code.append(f"    mov {ret_reg}, %r11  # _result (grej)")
    
    has_exit = False
    for stmt in stmts:
        compile_stmt(stmt)
        if stmt[0] == 'EXIT':
            has_exit = True

    if not has_exit:
        code.append(f"    xor %eax, %eax")
        emit_func_epilogue()

    for stmt in pending_real_funcs:
        compile_real_func(stmt[1], stmt[2], stmt[3])

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
    data.append("_hiuh_incl_mode: .asciz \"r\"")
    for buf in sorted(named_buffers):
        if buf != 'input_buf':
            data.append(f"{buf}: .skip 256")
    for buf in sorted(text_bufs.values()):
        data.append(f"{buf}: .skip 256")
    if target == 'linux' and skriv_buf_used[0]:
        data.append('_nl: .ascii "\\n"')
    data.append(".bss")
    data.append(".align 8")
    data.append("stack: .skip 4096")
    data.append("_hiuh_incl_buf: .skip 65536")
    data.append("_hiuh_incl_pos: .quad 0")
    data.append("_hiuh_incl_end: .quad 0")
    data.append("_hiuh_incl_fp: .skip 8")
    
    out = []
    out.append(".text")
    if target == 'windows':
        out.append(".globl main")
        out.append("main:")
        out.append("    push %r12")
        out.append("    push %r13")
        out.append("    push %rbp")
        out.append("    subq $32, %rsp  # shadow space")
        out.append("    mov $65001, %ecx")
        out.append("    call SetConsoleOutputCP")
        out.append("    lea stack(%rip), %r14  # init stack ptr")
    else:
        out.append(".globl _start")
        out.append("_start:")
        out.append("    call main")
        out.append("    xor %edi, %edi")
        out.append("    mov $60, %rax")
        out.append("    syscall")
        out.append("main:")
        out.append("    push %r12")
        out.append("    push %r13")
        out.append("    push %rbp")
        out.append("    lea stack(%rip), %r14  # init stack ptr")
    out.extend(code)
    out.append("")
    out.extend(data)
    
    return '\n'.join(out)

def preprocess(src, base_dir, _seen=None):
    if _seen is None:
        _seen = set()
    lines = src.splitlines()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('Inkludera '):
            filename = stripped[len('Inkludera '):].strip()
            path = os.path.join(base_dir, filename)
            real = os.path.realpath(path)
            if real in _seen:
                raise RuntimeError(f"Inkludera: cirkulär inkludering av '{filename}'")
            _seen.add(real)
            inc_src = open(path, encoding='utf-8').read()
            inc_dir = os.path.dirname(real)
            out.append(preprocess(inc_src, inc_dir, _seen))
            _seen.discard(real)
        else:
            out.append(line)
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
        base_dir = os.getcwd()
    elif sys.argv[1] == '--asm' or sys.argv[1] == '--ord-lista':
        src = open(sys.argv[2], encoding='utf-8').read()
        base_dir = os.path.dirname(os.path.realpath(sys.argv[2]))
    else:
        src = open(sys.argv[1], encoding='utf-8').read()
        base_dir = os.path.dirname(os.path.realpath(sys.argv[1]))

    src = preprocess(src, base_dir)
    result = tokenize(src)
    if isinstance(result, tuple):
        tokens, ord_lista = result
    else:
        tokens = result
        ord_lista = []
    use_windows = '--windows' in sys.argv or sys.platform == 'win32'
    target = 'windows' if use_windows else 'linux'

    stmts = parse(tokens)
    try:
        asm = compile_to_asm(stmts, target=target)
    except RuntimeError as e:
        print(f"Kompileringsfel: {e}", file=sys.stderr)
        sys.exit(1)

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