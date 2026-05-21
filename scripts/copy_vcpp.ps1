$destX64 = "E:\ClaudeCode\seb-bypass\vcpp-files\x64"
$destX86 = "E:\ClaudeCode\seb-bypass\vcpp-files\x86"
New-Item -ItemType Directory -Path $destX64 -Force | Out-Null
New-Item -ItemType Directory -Path $destX86 -Force | Out-Null

# x64 DLLs
Copy-Item "C:\Windows\System32\msvcp140.dll" -Destination "$destX64\msvcp140.dll" -Force
Copy-Item "C:\Windows\System32\vcruntime140.dll" -Destination "$destX64\vcruntime140.dll" -Force
Copy-Item "C:\Windows\System32\vcruntime140_1.dll" -Destination "$destX64\vcruntime140_1.dll" -Force

# x86 DLLs
Copy-Item "C:\Windows\SysWOW64\msvcp140.dll" -Destination "$destX86\msvcp140.dll" -Force
Copy-Item "C:\Windows\SysWOW64\vcruntime140.dll" -Destination "$destX86\vcruntime140.dll" -Force

Write-Output "=== x64 ==="
Get-ChildItem $destX64 | Format-Table Name,Length -AutoSize
Write-Output "=== x86 ==="
Get-ChildItem $destX86 | Format-Table Name,Length -AutoSize
