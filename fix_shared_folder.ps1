$vmxPath = "C:\Users\26502\Documents\Virtual Machines\Windows 10 x64\Windows 10 x64.vmx"
$content = Get-Content $vmxPath -Raw
$content = $content -replace 'isolation.tools.hgfs.disable = "TRUE"', 'isolation.tools.hgfs.disable = "FALSE"'
[System.IO.File]::WriteAllText($vmxPath, $content, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Done! Shared folders enabled."
Write-Host "Now: Shutdown VM -> Start VM -> Set shared folders"
