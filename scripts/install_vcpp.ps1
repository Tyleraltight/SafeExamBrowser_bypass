# Run this script INSIDE the VM with Admin privileges
# It copies VC++ runtime DLLs and creates registry entries

$source = "\\vmware-host\Shared Folders\seb-bypass\vcpp-files"

Write-Output "=== Copying x64 DLLs ==="
Copy-Item "$source\x64\msvcp140.dll" "C:\Windows\System32\msvcp140.dll" -Force
Copy-Item "$source\x64\vcruntime140.dll" "C:\Windows\System32\vcruntime140.dll" -Force
Copy-Item "$source\x64\vcruntime140_1.dll" "C:\Windows\System32\vcruntime140_1.dll" -Force
Write-Output "x64 DLLs copied to System32"

Write-Output "=== Copying x86 DLLs ==="
Copy-Item "$source\x86\msvcp140.dll" "C:\Windows\SysWOW64\msvcp140.dll" -Force
Copy-Item "$source\x86\vcruntime140.dll" "C:\Windows\SysWOW64\vcruntime140.dll" -Force
Write-Output "x86 DLLs copied to SysWOW64"

Write-Output "=== Creating registry entries ==="
# Mark VC++ 2015-2022 (14.0) as installed
$regPath = "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "Version" -Value "14.40.33810.0"
Set-ItemProperty -Path $regPath -Name "Installed" -Value 1
Set-ItemProperty -Path $regPath -Name "Major" -Value 14
Set-ItemProperty -Path $regPath -Name "Minor" -Value 40

$regPath86 = "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x86"
New-Item -Path $regPath86 -Force | Out-Null
Set-ItemProperty -Path $regPath86 -Name "Version" -Value "14.40.33810.0"
Set-ItemProperty -Path $regPath86 -Name "Installed" -Value 1
Set-ItemProperty -Path $regPath86 -Name "Major" -Value 14
Set-ItemProperty -Path $regPath86 -Name "Minor" -Value 40

# Also set the uninstall registry
$uninstall = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{a1b2c3d4-e5f6-7890-abcd-ef1234567890}"
New-Item -Path $uninstall -Force | Out-Null
Set-ItemProperty -Path $uninstall -Name "DisplayName" -Value "Microsoft Visual C++ 2015-2022 Redistributable (x64)"
Set-ItemProperty -Path $uninstall -Name "Publisher" -Value "Microsoft Corporation"

Write-Output ""
Write-Output "=== VC++ Runtime Installed ==="
Write-Output "Now try installing SEB again!"
