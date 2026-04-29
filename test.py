"""
HIUH test runner.

Direct tests: compiled with hiuh-native.py, run, output checked.
Pipeline tests: tokenizer | parser -> assemble -> link -> run, output checked.

Usage:
    python test.py           # run all tests
    python test.py arith     # run tests whose name contains 'arith'
"""

import subprocess
import sys
import os
import tempfile
import threading

ROOT    = os.path.dirname(os.path.abspath(__file__))
AS      = r"G:\msys64\mingw64\bin\as.exe"
LD      = r"G:\msys64\mingw64\bin\ld.exe"
LD_LIBS = ["-lmingw32", "-lmsvcrt", "-lkernel32"]
COMPILER  = os.path.join(ROOT, "compiler", "hiuh-native.py")
TOKENIZER = os.path.join(ROOT, "hiuh-tokenizer.exe")
PARSER    = os.path.join(ROOT, "hiuh-parser.exe")

GREEN = "\033[32m"
RED   = "\033[31m"
RESET = "\033[0m"
BOLD  = "\033[1m"

def src(name):
    return os.path.join(ROOT, "src", name)

# ---------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------
# Expected output uses \n — comparison normalises \r\n -> \n automatically.
# stdin: optional bytes to feed to the executable.

DIRECT_TESTS = [
    # source file               expected stdout                    stdin
    (src("test-func.hiuh"),      "10\n",                           None),
    (src("test-rekursion.hiuh"), "120\n",                          None),
    (src("test-7vars.hiuh"),     "7\n",                            None),
    (src("test-oka-minska.hiuh"),"3\n2\nprefixsuffix\n",          None),
    (src("test-minus.hiuh"),     "7",                              None),
    (src("test-minus2.hiuh"),    "9",                              None),
    (src("test-texten.hiuh"),    "SEThej\n",                       None),
    (src("test-och.hiuh"),       "jne L42\nL42:\nprefix42suffix\n",None),
    (src("test-och-if.hiuh"),    "träff\nklar\n",                  None),
    (src("test-text.hiuh"),      "hej världen\nhej världen\n1\n0\n", None),
    (src("test-text-func.hiuh"), "hej\n1\n0\n",                   None),
    (src("test-las-text.hiuh"),  "rad1\nrad2\n",                   b"rad1\nrad2\n"),
]

PIPELINE_TESTS = [
    # source file                  expected stdout
    (src("test-arith-parser.hiuh"), "13\n7\n10\n"),
    (src("test-oka-parser.hiuh"),   "11\n"),
    (src("test-if-parser.hiuh"),    "5\n3\n"),
    (src("test-while-parser.hiuh"), "3\n1\n2\n"),
    (src("test-ltgt-parser.hiuh"),  "0\n1\n2\n3\n4\n10\n"),
    (src("test-read-parser.hiuh"),  "hejsan\nvarlden\n",   b"hejsan\nvarlden\n"),
    (src("test-jamfor-parser.hiuh"), "0\n1\n",             b"nope\nhej\n"),
    (src("test-lagra-parser.hiuh"),   "A\nB\n"),
    (src("test-tecken-parser.hiuh"),  "72\n105\n"),
    (src("test-jamforbuf-parser.hiuh"), "1\n0\n",  b"hej\n"),
    (src("test-kopiera-parser.hiuh"), "halloj\n",  b"halloj\n"),
    (src("test-func-parser.hiuh"),      "7\n"),
    (src("test-anropa-parser.hiuh"),    "5\n"),
    (src("test-inkludera.hiuh"),        "14\n"),
    (src("test-inte-parser.hiuh"),      "3\n2\n1\n0\n"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd, stdin_bytes=None, timeout=10):
    result = subprocess.run(
        cmd, input=stdin_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def normalise(raw_bytes):
    """Decode and normalise CRLF to LF."""
    return raw_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def compile_direct(src_path, exe_path):
    rc, out, err = run(["python", COMPILER, src_path, exe_path])
    if rc != 0:
        return False, (err or out).decode(errors="replace").strip()
    return True, ""


def assemble_and_link(asm_path, exe_path):
    obj = asm_path.replace(".s", ".o")
    rc, out, err = run([AS, "-o", obj, asm_path])
    if rc != 0:
        return False, (err or out).decode(errors="replace").strip()
    rc, out, err = run([LD, "-o", exe_path, obj] + LD_LIBS)
    if rc != 0:
        return False, (err or out).decode(errors="replace").strip()
    return True, ""


def compile_pipeline(src_path, asm_path, exe_path):
    with open(src_path, "rb") as f:
        source = f.read()

    src_dir = os.path.dirname(src_path)
    tok = subprocess.Popen([TOKENIZER], stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           cwd=src_dir)
    par = subprocess.Popen([PARSER], stdin=tok.stdout,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    tok.stdout.close()  # give par sole ownership of the read end

    def feed():
        tok.stdin.write(source)
        tok.stdin.close()

    t = threading.Thread(target=feed, daemon=True)
    t.start()
    asm_bytes, par_err = par.communicate()
    t.join()
    tok.wait()

    if tok.returncode != 0:
        return False, f"tokenizer exit {tok.returncode}"
    if par.returncode != 0:
        return False, f"parser exit {par.returncode}: {par_err.decode(errors='replace').strip()}"

    with open(asm_path, "wb") as f:
        f.write(asm_bytes)

    return assemble_and_link(asm_path, exe_path)

# ---------------------------------------------------------------------------
# Individual test runners
# ---------------------------------------------------------------------------

def run_direct(src_path, expected, stdin_bytes, tmpdir):
    name = os.path.basename(src_path)
    exe  = os.path.join(tmpdir, name + ".exe")

    ok, msg = compile_direct(src_path, exe)
    if not ok:
        return False, f"compile: {msg}"

    rc, stdout, _ = run([exe], stdin_bytes=stdin_bytes)
    got = normalise(stdout)
    if got == expected:
        return True, ""
    return False, f"expected {expected!r}, got {got!r}"


def run_pipeline(src_path, expected, tmpdir, stdin_bytes=None):
    name    = os.path.basename(src_path)
    asm     = os.path.join(tmpdir, name + ".s")
    out_exe = os.path.join(tmpdir, name + ".exe")

    ok, msg = compile_pipeline(src_path, asm, out_exe)
    if not ok:
        return False, f"build: {msg}"

    rc, stdout, _ = run([out_exe], stdin_bytes=stdin_bytes)
    got = normalise(stdout)
    if got == expected:
        return True, ""
    return False, f"expected {expected!r}, got {got!r}"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    filter_str = sys.argv[1] if len(sys.argv) > 1 else None
    passed = failed = skipped = 0

    print(f"{BOLD}Building pipeline tools...{RESET}")
    for s, exe in [("src/hiuh-tokenizer.hiuh", TOKENIZER),
                   ("src/hiuh-parser.hiuh",    PARSER)]:
        ok, msg = compile_direct(os.path.join(ROOT, s), exe)
        label = f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {label}  {os.path.basename(exe)}")
        if not ok:
            print(f"       {msg}")
            sys.exit(1)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:

        def suite(label, tests, runner):
            nonlocal passed, failed, skipped
            print(f"{BOLD}{label}{RESET}")
            for entry in tests:
                if len(entry) == 3:
                    src_path, expected, stdin_b = entry
                    kwargs = dict(stdin_bytes=stdin_b, tmpdir=tmpdir)
                else:
                    src_path, expected = entry
                    kwargs = dict(tmpdir=tmpdir)

                name = os.path.basename(src_path)
                if filter_str and filter_str not in name:
                    skipped += 1
                    continue

                print(f"  ...   {name}", end="", flush=True)
                ok, msg = runner(src_path, expected, **kwargs)
                if ok:
                    print(f"\r  {GREEN}PASS{RESET}  {name}")
                    passed += 1
                else:
                    print(f"\r  {RED}FAIL{RESET}  {name}  — {msg}")
                    failed += 1
            print()

        suite("Direct tests (hiuh-native.py)", DIRECT_TESTS,
              lambda s, e, stdin_bytes, tmpdir: run_direct(s, e, stdin_bytes, tmpdir))
        suite("Pipeline tests (tokenizer | parser)", PIPELINE_TESTS,
              lambda s, e, tmpdir, stdin_bytes=None: run_pipeline(s, e, tmpdir, stdin_bytes))

    total = passed + failed
    color = GREEN if failed == 0 else RED
    summary = f"{passed}/{total} passed"
    if skipped:
        summary += f", {skipped} skipped"
    print(f"{color}{BOLD}{summary}{RESET}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
