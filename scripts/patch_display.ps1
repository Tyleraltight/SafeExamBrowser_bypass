# SEB Display Check Bypass Patcher
# This script patches SafeExamBrowser.Monitoring.dll to bypass display validation

param(
    [string]$DllPath = "C:\Program Files\SafeExamBrowser\Application\SafeExamBrowser.Monitoring.dll"
)

Write-Host ""
Write-Host "  SEB Display Check Bypass Patcher v2.0" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $DllPath)) {
    Write-Host "[ERROR] File not found: $DllPath" -ForegroundColor Red
    exit 1
}

# Create backup
$backupPath = "$DllPath.original"
if (-not (Test-Path $backupPath)) {
    Copy-Item $DllPath $backupPath
    Write-Host "[+] Created backup: $backupPath" -ForegroundColor Green
}

# Read the DLL
$dllBytes = [System.IO.File]::ReadAllBytes($DllPath)
Write-Host "[*] Loaded DLL: $($dllBytes.Length) bytes" -ForegroundColor Yellow

# Find key strings to identify the assembly version
function Find-Bytes {
    param($haystack, $needle, $startOffset = 0)
    for ($i = $startOffset; $i -le ($haystack.Length - $needle.Length); $i++) {
        $match = $true
        for ($j = 0; $j -lt $needle.Length; $j++) {
            if ($haystack[$i + $j] -ne $needle[$j]) {
                $match = $false
                break
            }
        }
        if ($match) { return $i }
    }
    return -1
}

function Find-All-Bytes {
    param($haystack, $needle)
    $results = @()
    $offset = 0
    while ($true) {
        $pos = Find-Bytes -haystack $haystack -needle $needle -startOffset $offset
        if ($pos -eq -1) { break }
        $results += $pos
        $offset = $pos + 1
    }
    return $results
}

# Search for key patterns
$patterns = @{
    "WmiMonitorBasicDisplayParams" = [System.Text.Encoding]::UTF8.GetBytes("WmiMonitorBasicDisplayParams")
    "WmiMonitorConnectionParams" = [System.Text.Encoding]::UTF8.GetBytes("WmiMonitorConnectionParams")
    "Failed to validate display" = [System.Text.Encoding]::UTF8.GetBytes("Failed to validate display")
    "Display configuration is not valid" = [System.Text.Encoding]::UTF8.GetBytes("Display configuration is not valid")
    "display configuration is valid" = [System.Text.Encoding]::UTF8.GetBytes("display configuration is valid")
    "Ignoring error" = [System.Text.Encoding]::UTF8.GetBytes("ignoring error")
    "errors are not allowed" = [System.Text.Encoding]::UTF8.GetBytes("errors are not allowed")
    "Root\WMI" = [System.Text.Encoding]::UTF8.GetBytes("Root\WMI")
    "VirtualMachineDetector" = [System.Text.Encoding]::UTF8.GetBytes("VirtualMachineDetector")
    "IsVirtualMachine" = [System.Text.Encoding]::UTF8.GetBytes("IsVirtualMachine")
}

Write-Host ""
Write-Host "[*] Searching for patterns in DLL..." -ForegroundColor Yellow

$foundPatterns = @{}
foreach ($name in $patterns.Keys) {
    $positions = Find-All-Bytes -haystack $dllBytes -needle $patterns[$name]
    if ($positions.Count -gt 0) {
        $foundPatterns[$name] = $positions
        Write-Host "  [+] $name : found at offsets $($positions -join ', ')" -ForegroundColor Green
    } else {
        Write-Host "  [-] $name : not found" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "[*] Analysis complete." -ForegroundColor Yellow
Write-Host ""
Write-Host "To patch the DLL, we need to modify the ValidateConfiguration method." -ForegroundColor Cyan
Write-Host "The method uses WMI queries that fail in VMware environments." -ForegroundColor Cyan
Write-Host ""
Write-Host "=== SOLUTION: Create a custom .seb config ===" -ForegroundColor Magenta
Write-Host ""
Write-Host "The simplest fix is to modify the .seb configuration file" -ForegroundColor White
Write-Host "to set 'allowedDisplaysIgnoreFailure' to true." -ForegroundColor White
Write-Host ""

# Check if we can find any .seb config files
$sebFiles = Get-ChildItem -Path "C:\","D:\","E:\" -Recurse -Filter "*.seb" -ErrorAction SilentlyContinue -Depth 3
if ($sebFiles) {
    Write-Host "Found .seb files:" -ForegroundColor Green
    foreach ($f in $sebFiles) {
        Write-Host "  $($f.FullName) ($($f.Length) bytes)" -ForegroundColor White
    }
} else {
    Write-Host "No .seb files found in common locations." -ForegroundColor Yellow
}
