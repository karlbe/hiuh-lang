#!/usr/bin/env python3
"""
Extract tokenizer logic from hiuh-native.py for comparison testing.
Allows comparing Python tokenizer output with HIUH tokenizer output.
"""

import sys
import os

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
    """Tokenize HIUH source code. Returns (tokens, ord_lista)."""
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
            elif 'skifta vänster' in rest:
                parts = rest.split('skifta vänster', 1)
                left = parts[0].strip()
                amount = parts[1].strip()
                tokens.append(('SHL', var, left, amount))
            elif 'skifta höger' in rest:
                parts = rest.split('skifta höger', 1)
                left = parts[0].strip()
                amount = parts[1].strip()
                tokens.append(('SHR', var, left, amount))
            elif ' band ' in rest:
                parts = rest.split(' band ', 1)
                left = parts[0].strip()
                right = parts[1].strip()
                tokens.append(('BAND', var, left, right))
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


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python hiuh_tokenizer_py.py <source.hiuh>")
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        src = f.read()

    tokens, _ = tokenize(src)
    for token in tokens:
        print(token)
