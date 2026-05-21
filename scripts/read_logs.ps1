$logPath = "$env:LOCALAPPDATA\SafeExamBrowser\Logs"
$latest = Get-ChildItem $logPath -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 3
foreach ($f in $latest) {
    Write-Host "=== $($f.Name) ===" -ForegroundColor Yellow
    Get-Content $f.FullName -Tail 30
    Write-Host ""
}
