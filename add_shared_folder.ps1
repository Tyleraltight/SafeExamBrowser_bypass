$vmxPath = "C:\Users\26502\Documents\Virtual Machines\Windows 10 x64\Windows 10 x64.vmx"
$content = Get-Content $vmxPath -Raw

$sharedFolder = @"
.sharedFolder0.guestName = "seb-bypass"
.sharedFolder0.hostPath = "E:\ClaudeCode\seb-bypass"
.sharedFolder0.readOnly = "FALSE"
.sharedFolder0.enabled = "TRUE"
.sharedFolder0.fldNumFileAccess = "0"
.sharedFolder0.fldName = "seb-bypass"
folderShareManager.sharedFolderList.sharedFolder0.present = "TRUE"
folderShareManager.sharedFolderList.sharedFolder0.name = "seb-bypass"
folderShareManager.sharedFolderList.sharedFolder0.path = "E:\ClaudeCode\seb-bypass"
folderShareManager.sharedFolderList.sharedFolder0.type = "0"
folderShareManager.sharedFolderList.sharedFolder0.nfro = "FALSE"
folderShareManager.numFolders = "1"
"@

$content = $content + "`n" + $sharedFolder
[System.IO.File]::WriteAllText($vmxPath, $content, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Shared folder added directly to .vmx!"
Write-Host "Path: E:\ClaudeCode\seb-bypass"
Write-Host "Guest access: \\vmware-host\Shared Folders\seb-bypass"
