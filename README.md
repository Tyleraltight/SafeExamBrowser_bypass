# Safe Exam Browser (SEB) v3.10.1 Bypass Toolkit

**English | [中文](README_zh.md)**

A toolkit for running Safe Exam Browser inside a VMware virtual machine. Bypasses SEB's VM detection and display validation through IL patching of `SafeExamBrowser.Monitoring.dll`.

## How It Works

```
Host Machine (your real computer)
│
│  Chrome / Edge / any app  ← completely free, no restrictions
│
│  ┌─────────────────────────────────┐
│  │  VMware Workstation (window)     │
│  │  ┌─────────────────────────────┐│
│  │  │  Windows 10 VM              ││
│  │  │  ┌─────────────────────┐   ││
│  │  │  │  SEB (patched)       │   ││
│  │  │  │  Thinks it's on a    │   ││
│  │  │  │  real machine        │   ││
│  │  │  └─────────────────────┘   ││
│  │  └─────────────────────────────┘│
│  └─────────────────────────────────┘
```

**Two patchers do the heavy lifting:**

1. **`seb-patcher`** (dnlib) — Patches `VirtualMachineDetector` class. Makes all 7 VM detection methods return `false`.

2. **`display-patcher`** (Mono.Cecil) — Patches `DisplayMonitor.TryLoadDisplays()` to return a fake internal display, and `ValidateConfiguration` to return `IsAllowed=true`. This solves the "0 displays detected" error that occurs in VMware.

## Prerequisites

| Software | Purpose |
|---|---|
| VMware Workstation 26H1 (or newer) | Virtualization |
| Windows 10/11 ISO | OS for the VM |
| .NET 9.0 SDK | Only if building from source |
| Python 3.10+ | Only for the analysis tools |
| SEB v3.10.1 installer | From your institution |

## Quick Start

### 1. Set Up VMware

1. Download and install [VMware Workstation Player](https://www.vmware.com/go/getplayer-win) (free)
2. Create a new Windows 10/11 virtual machine
3. Install Windows in the VM

### 2. Configure VM (Host Side)

Edit the `.vmx` file of your VM (with VMware closed):

```
firmware = "bios"
smbios.reflecthost = "TRUE"
hypervisor.cpuid.v0 = "FALSE"
monitor.virtual_exec = "hardware"
```

Key settings:
- `firmware = "bios"` — EFI mode causes ISO boot failures
- `smbios.reflecthost = "TRUE"` — Hides VMware BIOS strings

### 3. Install VMware Tools (Inside VM)

In VMware menu: **VM → Install VMware Tools** → run `setup64.exe` inside the VM → restart.

This enables auto-resolution, clipboard sharing, and drag-and-drop.

### 4. Install SEB Dependencies (Inside VM)

SEB v3.10.1 requires:
- **.NET Framework 4.8** — usually pre-installed on Windows 10 1903+
- **Visual C++ 2015-2022 Redistributable** — download from [Microsoft](https://aka.ms/vs/17/release/vc_redist.x64.exe)

If downloading inside the VM is too slow, use the host-to-VM approach:
1. Download `vc_redist.x64.exe` on your host machine
2. Place it in a shared folder accessible by the VM
3. Run it inside the VM

### 5. Install SEB (Inside VM)

Copy the SEB installer into the VM and run it normally.

### 6. Patch the DLL

**Option A: Use pre-compiled binaries (recommended)**

Copy the `bin/final/` directory into the VM (via shared folder), then run in an **Admin CMD**:

```cmd
cd <path-to-bin\final>
DisplayPatcher.exe
```

Then run the replacement script (Admin CMD):

```cmd
cd <path-to-scripts>
force_replace.cmd
```

The `force_replace.cmd` script needs to be adjusted if your paths differ. Edit it to point to the correct location of the patched DLL.

**Option B: Build from source**

```bash
cd display-patcher
dotnet publish -c Release -r win-x64 --self-contained true
```

Output will be in `display-patcher/bin/Release/net9.0/win-x64/publish/`.

### 7. Configure VMware Anti-Detection (Host Side)

Add these to your `.vmx` file:

```
smbios.reflecthost = "TRUE"
hypervisor.cpuid.v0 = "FALSE"
isolation.tools.hgfs.disable = "TRUE"
isolation.tools.dnd.disable = "TRUE"
isolation.tools.copy.disable = "TRUE"
isolation.tools.paste.disable = "TRUE"
monitor.virtual_exec = "hardware"
```

### 8. Test SEB

1. Open SEB inside the VM
2. It should no longer detect the virtual machine or report display issues
3. Verify fullscreen mode works properly

### 9. Exam Day

1. Open VMware → start VM → fullscreen (`Ctrl+Alt+Enter`)
2. Open SEB → navigate to exam
3. Host machine is completely free for reference materials

**Switching shortcuts:**

| Action | Shortcut |
|---|---|
| Enter fullscreen | `Ctrl+Alt+Enter` |
| Exit fullscreen | `Ctrl+Alt+Enter` (toggle) |
| Switch to host | `Ctrl+Alt+Enter` → click host taskbar |

## Project Structure

```
SafeExamBrowser_bypass/
├── README.md
├── .gitignore
├── requirements.txt              # Python dependencies
│
├── tools/                        # Python analysis tools
│   ├── main.py                   # CLI entry point
│   ├── utils.py                  # Shared utilities
│   ├── config_analyzer.py        # .seb config file decryptor/parser
│   ├── env_detector.py           # VM/remote desktop/monitoring detection
│   ├── process_monitor.py        # SEB process analysis
│   ├── kbypass.py                # Keyboard/input restriction analysis
│   ├── dll_patcher.py            # Download pre-patched DLLs from nxvvvv repo
│   ├── log_cleaner.py            # Sanitize SEB logs (remove VM traces)
│   └── vmx_helper.py             # VMware VMX configuration helper
│
├── seb-patcher/                  # dnlib-based IL patcher (VM detection)
│   ├── seb-patcher.csproj
│   └── Program.cs
│
├── display-patcher/              # Mono.Cecil IL patcher (display validation)
│   ├── DisplayPatcher.csproj
│   └── Program.cs
│
├── bin/final/                    # Pre-compiled display patcher (self-contained)
│   └── DisplayPatcher.exe        # Ready to use, no .NET SDK needed
│
├── scripts/                      # Helper scripts
│   ├── force_replace.cmd         # Force-replace DLL in SEB directory
│   ├── check_dll.cmd             # Diagnostic: check if patch succeeded
│   ├── fix_display.cmd           # Alternative DLL replacement script
│   ├── install_vcpp.ps1          # Install VC++ runtime in VM
│   ├── copy_vcpp.ps1             # Extract VC++ DLLs from host
│   └── read_logs.ps1             # Quick log viewer
│
└── bypass/                       # Runtime bypass modules (experimental)
    ├── hook_bypass.py            # Keyboard hook bypass (5 methods)
    ├── window_bypass.py          # Window manipulation (resize, minimize, hide)
    └── clipboard_bypass.py       # Clipboard access restoration
```

## Python Analysis Tools Usage

```bash
pip install -r requirements.txt

python tools/main.py scan                 # Full environment scan
python tools/main.py config -f exam.seb   # Analyze .seb config file
python tools/main.py env                  # Environment detection only
python tools/main.py monitor              # SEB process monitoring
python tools/main.py keys                 # Keyboard/input analysis
python tools/main.py patch                # Download & apply DLL patch
python tools/main.py patch --check        # Check patch status
python tools/main.py patch --restore      # Restore original files
python tools/main.py vmx                  # Check VMware anti-detection
python tools/main.py vmx --apply          # Apply anti-detection settings
python tools/main.py logs --scan          # Scan SEB logs for VM traces
python tools/main.py logs                 # Clean SEB logs
```

## Troubleshooting

We hit every single one of these during development. Learn from our pain.

### VMware won't boot from ISO

**Symptom:** "EFI Network... Time out" or boot loops.

**Cause:** VMware defaults to EFI firmware, which has poor CD-ROM boot support.

**Fix:** In the `.vmx` file, set `firmware = "bios"`. VMware must be completely closed before editing. If the "Exit Workstation" option is greyed out, use Task Manager to kill all VMware processes.

### Suspend file conflict after changing firmware

**Symptom:** "An error occurred while restoring the virtual machine state."

**Cause:** Changing EFI → BIOS invalidates the suspend file (`.vmss`).

**Fix:** Delete the `.vmss` and `.vmsd` files in the VM directory.

### SEB installer stuck at "Processing: VC++ Runtime"

**Cause:** VC++ installer runs silently in the background and may pop up UAC dialogs hidden behind other windows.

**Fix:**
1. Press `Alt+Tab` in the VM to check for hidden windows
2. If stuck, cancel and retry
3. Or pre-install VC++ from Microsoft's website before running SEB installer

### .NET Framework 4.8 missing

**Symptom:** SEB installer shows `.NET Framework 4.8` as not installed.

**Cause:** Fresh Windows 10 VM may not have it.

**Fix:** Windows 10 1903+ includes .NET 4.8 by default. Check with:
```powershell
(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full').Release
```
If value >= 528040, .NET 4.8 is installed.

### SEB detects virtual machine

**Symptom:** SEB shows "Safe Exam Browser has detected that the application is running on a virtual machine."

**Fix:** Run `seb-patcher` to patch the `VirtualMachineDetector` class. See [Quick Start step 6](#6-patch-the-dll).

### SEB reports "0 displays detected"

**Symptom:** "Display configuration is not allowed. 0 internal and 0 external displays."

**Cause:** SEB uses WMI (`WmiMonitorBasicDisplayParams`) to query display info, which doesn't work properly in VMware.

**Fix:** Run `display-patcher` to patch `TryLoadDisplays` and `ValidateConfiguration`. See [Quick Start step 6](#6-patch-the-dll).

### DLL is locked / cannot be replaced

**Symptom:** `force_replace.cmd` fails to copy the patched DLL.

**Cause:** A process is holding a lock on the file. Common culprits:
- `SafeExamBrowser.Service.exe` (Windows service, auto-restarts)
- `dnSpy.exe` (if you opened the DLL for inspection)
- `SafeExamBrowser.exe` (main process)

**Fix:**
```cmd
taskkill /f /im SafeExamBrowser* 2>nul
taskkill /f /im dnSpy* 2>nul
net stop SafeExamBrowser.Service 2>nul
timeout /t 3 /nobreak >nul
```

Then run the replacement script again.

### PowerShell execution policy blocks scripts

**Symptom:** "This system has disabled script execution."

**Fix:**
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
```

Or run scripts with:
```powershell
powershell -ExecutionPolicy Bypass -File "script.ps1"
```

### Shared folder path with spaces

**Symptom:** `\\vmware-host\Shared Folders\seb-bypass\script.cmd` fails with "syntax error."

**Cause:** CMD can't handle paths with spaces in UNC format.

**Fix:** Map to a drive letter first:
```cmd
net use Z: "\\vmware-host\Shared Folders\seb-bypass"
Z:\force_replace.cmd
```

### VMware Tools installed but resolution is wrong

**Fix:** In VMware menu: **View → Autosize → Adapt Guest**. Or manually set resolution inside the VM: right-click desktop → Display Settings → match your host screen resolution.

### SEB logs contain VMware traces

**Symptom:** SEB logs mention "VMware Virtual Platform" or "integrity compromised."

**Fix:** Use the log cleaner after exams:
```bash
python tools/main.py logs --scan    # Preview what will be cleaned
python tools/main.py logs           # Actually clean the logs
```

Or manually delete: `%LOCALAPPDATA%\SafeExamBrowser\Logs\*`

## Technical Details

### What gets patched in `SafeExamBrowser.Monitoring.dll`

**VirtualMachineDetector (by seb-patcher):**
```
IsVirtualMachine()    → return false
HasNoSystemHardware() → return false
HasVirtualDevice()    → return false
HasVirtualMacAddress()→ return false
IsVirtualCpu()        → return false
IsVirtualRegistry()   → return false
IsVirtualSystem()     → return false
```

**DisplayMonitor (by display-patcher):**
```
TryLoadDisplays()          → returns true + fake internal display list
ValidateConfiguration()    → returns ValidationResult(IsAllowed=true, InternalDisplays=1)
ValidateConfiguration λ*   → all related lambdas return true
WMI display methods        → return true (bypasses WmiMonitorBasicDisplayParams query)
```

### VideoOutputTechnology enum overflow

The `VideoOutputTechnology.Internal` enum value is `0x80000000` (Int32.MinValue). When writing IL, this must be handled as:
```csharp
long rawVal = Convert.ToInt64(internalField.Constant);
il.Append(il.Create(OpCodes.Ldc_I4, unchecked((int)rawVal)));
```
This was the cause of several crashes during development.

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| SEB logs contain `VMware Virtual Platform` | Medium | Clean logs before submitting |
| `Application integrity is compromised` in logs | Medium | SEB continues to run despite this warning |
| Moodle server sees integrity check failure | Low | Server only gets a pass/fail signal, not details |
| Teacher asks to submit SEB logs | High | Clean logs with `log_cleaner.py` or delete them |
| SEB updates and invalidates patches | Medium | Re-run patchers after SEB updates |
| VMware detection improves in newer SEB | Medium | Currently works with v3.10.1 |

## Building From Source

### seb-patcher (requires .NET 9.0 SDK)

```bash
cd seb-patcher
dotnet restore
dotnet publish -c Release -r win-x64 --self-contained true
```

### display-patcher (requires .NET 9.0 SDK)

```bash
cd display-patcher
dotnet restore
dotnet publish -c Release -r win-x64 --self-contained true
```

## Credits

- [nxvvvv/safe-exam-browser-bypass](https://github.com/nxvvvv/safe-exam-browser-bypass) — Original approach of DLL replacement, referenced for the patching strategy
- [SafeExamBrowser/seb-win-refactoring](https://github.com/SafeExamBrowser/seb-win-refactoring) — SEB source code (open source, GPL-3.0), used to understand detection mechanisms
- [dnlib](https://github.com/0xd4d/dnlib) — .NET assembly manipulation library
- [Mono.Cecil](https://github.com/jbevain/cecil) — IL manipulation library
