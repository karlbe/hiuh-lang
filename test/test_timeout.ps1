$p = Start-Process -FilePath "hiuh-tokenizer.exe" -NoNewWindow -PassThru
Start-Sleep 3
if (!$p.HasExited) {
    $p.Kill()
    Write-Output "HUNG"
} else {
    Write-Output "EXITED: $($p.ExitCode)"
}