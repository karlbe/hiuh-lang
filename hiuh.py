#!/usr/bin/env python3
"""
HIUH Compiler - Full feature set including arithmetic and comparisons
No special characters: no [], no +, no quotes!
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
        
        # ARITMETIK: x plus y, x minus y, x gånger y, x delat y
        elif len(words) >= 3:
            if 'plus' in words:
                idx = words.index('plus')
                left = ' '.join(words[:idx])
                right = ' '.join(words[idx+1:])
                tokens.append(('OP_PLUS', f'{left}:{right}', lineno))
            elif 'minus' in words:
                idx = words.index('minus')
                left = ' '.join(words[:idx])
                right = ' '.join(words[idx+1:])
                tokens.append(('OP_MINUS', f'{left}:{right}', lineno))
            elif 'gånger' in words:
                idx = words.index('gånger')
                left = ' '.join(words[:idx])
                right = ' '.join(words[idx+1:])
                tokens.append(('OP_MUL', f'{left}:{right}', lineno))
            elif 'delat' in words:
                idx = words.index('delat')
                left = ' '.join(words[:idx])
                right = ' '.join(words[idx+1:])
                tokens.append(('OP_DIV', f'{left}:{right}', lineno))
            else:
                tokens.append(('EXPR', stripped, lineno))
        
        # JÄMFÖRELSER: x är y, x är större än y, x är mindre än y
        elif 'är' in words and 'större' in words and 'än' in words:
            ei = words.index('är')
            si = words.index('större')
            ni = words.index('än')
            left = ' '.join(words[:ei])
            right = ' '.join(words[ni+1:])
            tokens.append(('CMP_GT', f'{left}:{right}', lineno))
        elif 'är' in words and 'mindre' in words and 'än' in words:
            ei = words.index('är')
            mi = words.index('mindre')
            ni = words.index('än')
            left = ' '.join(words[:ei])
            right = ' '.join(words[ni+1:])
            tokens.append(('CMP_LT', f'{left}:{right}', lineno))
        elif 'är' in words:
            ei = words.index('är')
            left = ' '.join(words[:ei])
            right = ' '.join(words[ei+1:])
            if right and right != 'större' and right != 'mindre':
                tokens.append(('CMP_EQ', f'{left}:{right}', lineno))
        
        # ELEMENT ... UR
        elif 'element' in words and 'ur' in words:
            try:
                ei = words.index('element')
                ui = words.index('ur')
                idx = ' '.join(words[ei+1:ui])
                target = ' '.join(words[ui+1:])
                tokens.append(('ELEMENT_UR', f'{idx}:{target}', lineno))
            except: pass
        
        # TECKEN ... UR
        elif 'tecken' in words and 'ur' in words:
            try:
                ti = words.index('tecken')
                ui = words.index('ur')
                idx = ' '.join(words[ti+1:ui])
                target = ' '.join(words[ui+1:])
                tokens.append(('TECKEN_UR', f'{idx}:{target}', lineno))
            except: pass
        
        # SAMMANFOGAT MED
        elif 'sammanfogat' in words and 'med' in words:
            try:
                si = words.index('sammanfogat')
                mi = words.index('med')
                left = ' '.join(words[:si])
                right = ' '.join(words[mi+1:])
                tokens.append(('SAMMANFOGAT', f'{left}:{right}', lineno))
            except: pass
        
        # ANTAL ELEMENT I
        elif first == 'Antal' and len(words) >= 4 and words[2] == 'element' and words[3] == 'i':
            target = ' '.join(words[4:])
            tokens.append(('ANTAL', target, lineno))
        
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
        elif typ in ('OP_PLUS', 'OP_MINUS', 'OP_MUL', 'OP_DIV'):
            parts = val.split(':')
            left = parts[0]
            right = parts[1] if len(parts) > 1 else ''
            stmts.append((typ, left, right))
            i += 1
        elif typ in ('CMP_GT', 'CMP_LT', 'CMP_EQ'):
            parts = val.split(':')
            left = parts[0]
            right = parts[1] if len(parts) > 1 else ''
            stmts.append((typ, left, right))
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
        elif typ == 'ELEMENT_UR':
            parts = val.split(':')
            stmts.append(('ELEMENT_UR', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'ANTAL':
            stmts.append(('ANTAL', val))
            i += 1
        elif typ == 'OM':
            body, else_b, i = parse_if(tokens, i)
            stmts.append(('OM', body, else_b))
        elif typ == 'FOR':
            parts = val.split(':')
            var, start, end = parts[0], parts[1] if len(parts) > 1 else '0', parts[2] if len(parts) > 2 else '10'
            body, i = parse_block(tokens, i + 1)
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
        elif typ == 'SKRIV_VAR':
            body.append(('SKRIV_VAR', tokens[i][1]))
            i += 1
        elif typ == 'SATT':
            parts = tokens[i][1].split(':', 1)
            body.append(('SATT', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ in ('OP_PLUS', 'OP_MINUS', 'OP_MUL', 'OP_DIV'):
            parts = tokens[i][1].split(':')
            body.append((typ, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ in ('CMP_GT', 'CMP_LT', 'CMP_EQ'):
            parts = tokens[i][1].split(':')
            body.append((typ, parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'LIST_NEW':
            body.append(('LIST_NEW', tokens[i][1]))
            i += 1
        elif typ == 'LIST_APPEND':
            parts = tokens[i][1].split(':')
            body.append(('LIST_APPEND', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'ELEMENT_UR':
            parts = tokens[i][1].split(':')
            body.append(('ELEMENT_UR', parts[0], parts[1] if len(parts) > 1 else ''))
            i += 1
        elif typ == 'ANTAL':
            body.append(('ANTAL', tokens[i][1]))
            i += 1
        elif typ == 'OM':
            then_b, else_b, i = parse_if(tokens, i)
            body.append(('OM', then_b, else_b))
        elif typ == 'FOR':
            parts = tokens[i][1].split(':')
            var = parts[0]
            start = parts[1] if len(parts) > 1 else '0'
            end = parts[2] if len(parts) > 2 else '10'
            loop_body, i = parse_block(tokens, i + 1)
            body.append(('FOR', var, start, end, loop_body))
        elif typ == 'EXIT':
            body.append(('EXIT', tokens[i][1]))
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

class Compiler:
    def __init__(self):
        self.strings = []
        self.variables = {}
        self.next_var_idx = 0
        self.code = []
        self.label_counter = 0
    
    def alloc_var(self, name):
        if name not in self.variables:
            self.variables[name] = self.next_var_idx
            self.next_var_idx += 1
        return self.variables[name]
    
    def get_var_idx(self, name):
        if name in self.variables:
            return self.variables[name]
        return None
    
    def new_label(self):
        self.label_counter += 1
        return f'L{self.label_counter}'
    
    def resolve_value(self, val):
        """Returns (is_var, value)"""
        try:
            return False, int(val)
        except:
            return True, val
    
    def compile_statement(self, stmt):
        op = stmt[0]
        
        if op == 'SKRIV':
            s = stmt[1]
            off = len(self.strings) * 64
            self.strings.append(s)
            self.code.append(f'    (call $fd_write (i32.const 1) (i32.const {off}) (i32.const {len(s)}) (i32.const 0))')
        
        elif op == 'SKRIV_VAR':
            var = stmt[1]
            if self.get_var_idx(var) is not None:
                self.code.append(f'    (call $print_i32 (global.get ${var}))')
            else:
                self.code.append(f'    ;; FEL: {var} är inte definierad')
        
        elif op == 'SATT':
            name = stmt[1]
            val = stmt[2]
            self.alloc_var(name)
            
            # Check for arithmetic operations
            is_var, resolved = self.resolve_value(val)
            
            if not is_var:
                self.code.append(f'    (global.set ${name} (i32.const {resolved}))')
            elif self.get_var_idx(val) is not None:
                self.code.append(f'    (global.set ${name} (global.get ${val}))')
            else:
                self.code.append(f'    ;; FEL: okänd variabel {val}')
        
        elif op in ('OP_PLUS', 'OP_MINUS', 'OP_MUL', 'OP_DIV'):
            # For Sätt x till a plus b, we need a temp var
            left, right = stmt[1], stmt[2]
            self.alloc_var('_tmp')
            
            # Load left
            is_var_l, val_l = self.resolve_value(left)
            if is_var_l:
                idx = self.get_var_idx(val_l)
                if idx is not None:
                    self.code.append(f'    (global.set $_tmp (global.get ${val_l}))')
                else:
                    self.code.append(f'    ;; FEL: okänd {val_l}')
            else:
                self.code.append(f'    (global.set $_tmp (i32.const {val_l}))')
            
            # Load right and apply op
            is_var_r, val_r = self.resolve_value(right)
            op_map = {'OP_PLUS': 'add', 'OP_MINUS': 'sub', 'OP_MUL': 'mul', 'OP_DIV': 'div_s'}
            wasm_op = op_map.get(op, 'add')
            
            if is_var_r:
                idx = self.get_var_idx(val_r)
                if idx is not None:
                    self.code.append(f'    (global.set $_tmp (i32.{wasm_op} (global.get $_tmp) (global.get ${val_r})))')
                else:
                    self.code.append(f'    ;; FEL: okänd {val_r}')
            else:
                self.code.append(f'    (global.set $_tmp (i32.{wasm_op} (global.get $_tmp) (i32.const {val_r})))')
        
        elif op in ('CMP_GT', 'CMP_LT', 'CMP_EQ'):
            left, right = stmt[1], stmt[2]
            is_var_l, val_l = self.resolve_value(left)
            is_var_r, val_r = self.resolve_value(right)
            
            self.alloc_var('_cmp_result')
            
            # Compare and set result (1 = true, 0 = false)
            op_map = {'CMP_GT': 'gt_s', 'CMP_LT': 'lt_s', 'CMP_EQ': 'eq'}
            wasm_op = op_map.get(op, 'eq')
            
            # Load left into tmp
            if is_var_l:
                self.code.append(f'    (global.set $_tmp (global.get ${val_l}))')
            else:
                self.code.append(f'    (global.set $_tmp (i32.const {val_l}))')
            
            # Compare
            if is_var_r:
                self.code.append(f'    (global.set $_cmp_result (select (i32.{wasm_op} (global.get $_tmp) (global.get ${val_r})) (i32.const 1) (i32.const 0)))')
            else:
                self.code.append(f'    (global.set $_cmp_result (select (i32.{wasm_op} (global.get $_tmp) (i32.const {val_r})) (i32.const 1) (i32.const 0)))')
        
        elif op == 'LIST_NEW':
            name = stmt[1]
            self.alloc_var(name)
            self.code.append(f'    (global.set ${name} (i32.const 0))')
        
        elif op == 'LIST_INIT':
            name = stmt[1]
            items_str = stmt[2]
            self.alloc_var(name)
            if items_str:
                items = [x.strip() for x in items_str.split(',')]
                ptr = 32768
                self.code.append(f'    (global.set ${name} (i32.const {ptr}))')
        
        elif op == 'LIST_APPEND':
            item, target = stmt[1], stmt[2]
            # Get item value
            is_var, val = self.resolve_value(item)
            self.alloc_var('_tmp')
            if is_var:
                if self.get_var_idx(val) is not None:
                    self.code.append(f'    (global.set $_tmp (global.get ${val}))')
                else:
                    self.code.append(f'    ;; FEL: okänd {val}')
            else:
                self.code.append(f'    (global.set $_tmp (i32.const {val}))')
            # Store at list pointer
            self.code.append(f'    (global.set $_tmp (i32.const 999))  ;; TODO: append to list')
        
        elif op == 'ANTAL':
            target = stmt[1]
            # Store list length (hardcoded for now, TODO)
            self.alloc_var('_result')
            self.code.append(f'    (global.set $_result (i32.const 0))  ;; Antal för {target}')
        
        elif op == 'ELEMENT_UR':
            idx_expr, target = stmt[1], stmt[2]
            # Get index
            is_var, val = self.resolve_value(idx_expr)
            self.alloc_var('_idx')
            if is_var:
                if self.get_var_idx(val) is not None:
                    self.code.append(f'    (global.set $_idx (global.get ${val}))')
                else:
                    self.code.append(f'    ;; FEL: okänd {val}')
            else:
                self.code.append(f'    (global.set $_idx (i32.const {val}))')
            # Load element at list[idx] = *(list_ptr + idx*4)
            self.code.append(f'    (global.set $_tmp (i32.load (i32.mul (global.get $_idx) (i32.const 4))))')
        
        elif op == 'TECKEN_UR':
            idx_expr, target = stmt[1], stmt[2]
            # Get index
            is_var, val = self.resolve_value(idx_expr)
            self.alloc_var('_idx')
            if is_var:
                if self.get_var_idx(val) is not None:
                    self.code.append(f'    (global.set $_idx (global.get ${val}))')
                else:
                    self.code.append(f'    ;; FEL: okänd {val}')
            else:
                self.code.append(f'    (global.set $_idx (i32.const {val}))')
            # Load byte at string[idx]
            self.code.append(f'    (global.set $_tmp (i32.load8_u (global.get $_idx)))')
        
        elif op == 'SAMMANFOGAT':
            left, right = stmt[1], stmt[2]
            # For now, just mark it
            self.code.append(f'    ;; {left} sammanfogat med {right}')
        
        elif op == 'OM':
            cond = stmt[1]
            then_body = stmt[2]
            else_body = stmt[3] if len(stmt) > 3 else []
            end_label = self.new_label()
            else_label = self.new_label() if else_body else end_label
            
            # Compile condition
            self.compile_statement(cond)
            
            # Jump if false (result == 0)
            self.code.append(f'    (if (i32.eqz (global.get $_cmp_result)) (then (br {else_label})))')
            
            for s in then_body:
                self.compile_statement(s)
            
            if else_body:
                self.code.append(f'    (br {end_label})')
                self.code.append(f'  {else_label}:')
                for s in else_body:
                    self.compile_statement(s)
            
            self.code.append(f'  {end_label}:')
        
        elif op == 'FOR':
            var = stmt[1]
            start = stmt[2]
            end = stmt[3]
            body = stmt[4]
            
            self.alloc_var(var)
            loop_start = self.new_label()
            loop_end = self.new_label()
            
            # Initialize
            try:
                start_val = int(start)
                self.code.append(f'    (global.set ${var} (i32.const {start_val}))')
            except:
                if self.get_var_idx(start) is not None:
                    self.code.append(f'    (global.set ${var} (global.get ${start}))')
                else:
                    self.code.append(f'    (global.set ${var} (i32.const 0))')
            
            # Loop start
            self.code.append(f'  {loop_start}:')
            
            # Check condition: var >= end
            try:
                end_val = int(end)
                self.code.append(f'    (if (i32.ge_s (global.get ${var}) (i32.const {end_val})) (then (br {loop_end})))')
            except:
                if self.get_var_idx(end) is not None:
                    self.code.append(f'    (if (i32.ge_s (global.get ${var}) (global.get ${end})) (then (br {loop_end})))')
                else:
                    self.code.append(f'    (if (i32.ge_s (global.get ${var}) (i32.const 0)) (then (br {loop_end})))')
            
            # Loop body
            for s in body:
                self.compile_statement(s)
            
            # Increment
            self.code.append(f'    (global.set ${var} (i32.add (global.get ${var}) (i32.const 1)))')
            self.code.append(f'    (br {loop_start})')
            self.code.append(f'  {loop_end}:')
        
        elif op == 'EXIT':
            code = stmt[1]
            self.code.append(f'    (call $proc_exit (i32.const {code}))')
    
    def generate_wat(self, statements):
        # Generate globals
        globals_section = "  (global $tmp (mut i32) (i32.const 0))\n"
        globals_section += "  (global $_cmp_result (mut i32) (i32.const 0))\n"
        globals_section += "  (global $_idx (mut i32) (i32.const 0))\n"
        globals_section += "  (global $_result (mut i32) (i32.const 0))\n"
        for name in sorted(self.variables.keys()):
            if not name.startswith('_'):
                globals_section += f"  (global ${name} (mut i32) (i32.const 0))\n"
        
        # Compile all statements
        for stmt in statements:
            self.compile_statement(stmt)
        
        # Build strings data
        strings_data = ""
        for i, s in enumerate(self.strings):
            off = i * 64
            escaped = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\0a')
            strings_data += f'    (data (i32.const {off}) "{escaped}\\00")\n'
        
        code_str = '\n'.join(self.code)
        
        return f"""(module
  (memory (export "memory") 1)

  (import "wasi_snapshot_preview1" "fd_write"
    (func $fd_write (param i32 i32 i32 i32) (result i32)))
  (import "wasi_snapshot_preview1" "proc_exit"
    (func $proc_exit (param i32)))

{globals_section}
  (func $print_i32 (param $v i32)
    (local $buf i32)
    (local $i i32)
    (local $digit i32)
    (local $n i32)
    (local.set $buf (i32.const 32768))
    (local.set $i (i32.const 0))
    (local.set $n (local.get $v))
    (if (i32.lt_s (local.get $n) (i32.const 0)) (then
      (i32.store8 (local.get $buf) (local.get $i) (i32.const 45))
      (local.set $i (i32.add (local.get $i) (i32.const 1)))
      (local.set $n (i32.sub (i32.const 0) (local.get $n)))
    ))
    (block $done
      (loop $loop
        (local.set $digit (i32.add (i32.const 48) (i32.rem_s (local.get $n) (i32.const 10))))
        (i32.store8 (local.get $buf) (local.get $i) (local.get $digit))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (local.set $n (i32.div_s (local.get $n) (i32.const 10)))
        (br_if $done (i32.eqz (local.get $n)))
      )
    )
    (call $fd_write (i32.const 1) (i32.sub (local.get $buf) (local.get $i)) (local.get $i) (i32.const 0))
  )

  (func (export "_start")
{code_str}
  )

{strings_data})"""

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
    compiler = Compiler()
    wat = compiler.generate_wat(stmts)
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