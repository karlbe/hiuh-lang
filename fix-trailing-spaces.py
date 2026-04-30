"""
fix-trailing-spaces.py — replaces SPACE placeholder with actual trailing space
in .hiuh source files. Run this manually after editing sources that need
trailing spaces (e.g. `Skriv lea SPACE` → `Skriv lea `).

Usage:
    python fix-trailing-spaces.py [file ...]
    python fix-trailing-spaces.py          # fixes all src/*.hiuh
"""
import sys, os, glob

PLACEHOLDER = "SPACE"

def fix_file(path):
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()
    fixed = original.replace(PLACEHOLDER, " ")
    if fixed != original:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(fixed)
        print(f"Fixed: {path}")
    else:
        print(f"No change: {path}")

if len(sys.argv) > 1:
    files = sys.argv[1:]
else:
    root = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(os.path.join(root, "src", "*.hiuh"))

for f in files:
    fix_file(f)
