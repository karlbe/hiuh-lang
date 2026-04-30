param([Parameter(Mandatory)][string]$Source, [switch]$Asm)

$root   = $PSScriptRoot
$base   = [System.IO.Path]::GetFileNameWithoutExtension($Source)
$srcAbs = Resolve-Path $Source
$dir    = Split-Path $srcAbs
$out    = Join-Path $dir "$base.exe"

if ($Asm) {
    python "$root\compiler\hiuh-native.py" --asm $srcAbs
} else {
    python "$root\compiler\hiuh-native.py" $srcAbs $out
}
