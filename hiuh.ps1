param([Parameter(Mandatory)][string]$Source, [switch]$Asm, [switch]$Py)

$root   = $PSScriptRoot
$base   = [System.IO.Path]::GetFileNameWithoutExtension($Source)
$srcAbs = Resolve-Path $Source
$dir    = Split-Path $srcAbs
$out    = Join-Path $dir "$base.exe"

if ($Py) {
    if ($Asm) {
        python "$root\compiler\hiuh-native.py" --asm $srcAbs
    } else {
        python "$root\compiler\hiuh-native.py" $srcAbs $out
    }
    exit 0
}

$tok     = "$root\hiuh-tokenizer.exe"
$par     = "$root\hiuh-parser.exe"
$as      = "G:\msys64\mingw64\bin\as.exe"
$ld      = "G:\msys64\mingw64\bin\ld.exe"
$asmFile = Join-Path $dir "$base.s"
$obj     = Join-Path $dir "$base.o"

cmd /c "cd /d `"$dir`" && `"$tok`" < `"$srcAbs`" | `"$par`" > `"$asmFile`""
if ($LASTEXITCODE -ne 0) { Write-Error "Parse failed"; exit 1 }

if ($Asm) { Get-Content $asmFile; Remove-Item $asmFile; exit 0 }

& $as -o $obj $asmFile
if ($LASTEXITCODE -ne 0) { Write-Error "Assemble failed"; exit 1 }

& $ld -o $out $obj -lmingw32 -lmsvcrt -lkernel32
if ($LASTEXITCODE -ne 0) { Write-Error "Link failed"; exit 1 }

Remove-Item $asmFile, $obj -ErrorAction SilentlyContinue
Write-Host "Kompilerade till $out"
