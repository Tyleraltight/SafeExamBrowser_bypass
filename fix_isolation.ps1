$vmxPath = "C:\Users\26502\Documents\Virtual Machines\Windows 10 x64\Windows 10 x64.vmx"
$content = Get-Content $vmxPath -Raw

# Enable copy/paste between host and VM
$content = $content -replace 'isolation.tools.copy.disable = "TRUE"', 'isolation.tools.copy.disable = "FALSE"'
$content = $content -replace 'isolation.tools.paste.disable = "TRUE"', 'isolation.tools.paste.disable = "FALSE"'
# Enable drag and drop
$content = $content -replace 'isolation.tools.dnd.disable = "TRUE"', 'isolation.tools.dnd.disable = "FALSE"'
# Enable shared folders (HGFS)
$content = $content -replace 'isolation.tools.hgfs.disable = "TRUE"', 'isolation.tools.hgfs.disable = "FALSE"'

[System.IO.File]::WriteAllText($vmxPath, $content, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Done! Copy/paste, drag-drop, shared folders all enabled."
Write-Host "Restart VM for changes to take effect."
