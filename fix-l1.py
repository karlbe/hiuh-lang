# fix-l1.py — insert REAL_INIT: label into parser2.s
#
# The generated main: does "jmp do_parse_init".
# do_parse_init: initializes and then does "jmp REAL_INIT".
# REAL_INIT: needs to be placed at the start of the actual main loop
# (right after the puts("jmp do_parse_init") output call).
#
# Detection: find the .asciz "jmp do_parse_init" string, then find
# the "pop %r8" that ends the puts() call for it, and insert REAL_INIT:
# on the NEXT line.

import sys
import re

def main():
    with open('parser2.s', 'r') as f:
        lines = f.readlines()

    # Check if REAL_INIT: already exists
    for line in lines:
        if line.strip() == 'REAL_INIT:':
            print("REAL_INIT: already present in parser2.s")
            return

    # Strategy: find ".asciz "jmp do_parse_init"" then find the next "pop %r8"
    # and insert REAL_INIT: after it
    asciz_idx = None
    for i, line in enumerate(lines):
        if '.asciz' in line and 'jmp do_parse_init' in line:
            asciz_idx = i
            print(f"Found .asciz 'jmp do_parse_init' at line {i+1}")
            break

    if asciz_idx is None:
        print("ERROR: Could not find .asciz 'jmp do_parse_init'")
        sys.exit(1)

    # Find the next "pop %r8" after asciz_idx
    insert_at = None
    for i in range(asciz_idx, min(asciz_idx + 20, len(lines))):
        if lines[i].strip() == 'pop %r8':
            insert_at = i + 1  # insert AFTER the pop %r8
            print(f"Found pop %r8 at line {i+1}, inserting REAL_INIT: at line {i+2}")
            break

    if insert_at is None:
        print("ERROR: Could not find pop %r8 after asciz")
        sys.exit(1)

    lines.insert(insert_at, 'REAL_INIT:\n')

    with open('parser2.s', 'w') as f:
        f.writelines(lines)

    print("Done: inserted REAL_INIT: into parser2.s")

if __name__ == '__main__':
    main()
