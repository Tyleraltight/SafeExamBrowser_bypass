$vmxPath = "C:\Users\26502\Documents\Virtual Machines\Windows 10 x64\Windows 10 x64.vmx"
$content = Get-Content $vmxPath -Raw

# Change EFI to BIOS
$content = $content -replace 'firmware = "efi"', 'firmware = "bios"'

# Add anti-detection settings
$newLines = @(
    ""
    "# Anti-detection settings"
    'smbios.reflecthost = "TRUE"'
    'hypervisor.cpuid.v0 = "FALSE"'
    'isolation.tools.hgfs.disable = "TRUE"'
    'isolation.tools.dnd.disable = "TRUE"'
    'isolation.tools.copy.disable = "TRUE"'
    'isolation.tools.paste.disable = "TRUE"'
    'monitor.virtual_exec = "hardware"'
)

$content = $content + "`n" + ($newLines -join "`n")
[System.IO.File]::WriteAllText($vmxPath, $content, (New-Object System.Text.UTF8Encoding $false))

Write-Host ".vmx updated successfully!"
Write-Host "Changes:"
Write-Host "  - firmware: efi -> bios"
Write-Host "  - Added 7 anti-detection settings"
