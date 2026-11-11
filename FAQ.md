# Frequently Asked Questions (FAQ)

**[English](FAQ.md) | [中文](FAQ_zh.md)**

## General

### What is this tool?

A toolkit for running Safe Exam Browser (SEB) inside a VMware virtual machine. It patches SEB's monitoring DLL to bypass VM detection and display validation, allowing you to run SEB in a VM while keeping your host machine free.

### Does this actually work?

Yes. We've tested it on SEB v3.10.1.864 with Moodle integration. The patcher disables all 7 VM detection methods and resolves the "0 displays" error that VMware causes.

### Which SEB versions are supported?

Currently **SEB v3.10.1 and v3.10.2**. Other v3.x versions may work but are not tested. SEB v3.6.x requires a different patcher (see [nxvvvv/safe-exam-browser-bypass](https://github.com/nxvvvv/safe-exam-browser-bypass)).

### Does this work on macOS or Linux?

No. This toolkit is Windows-only. The SEB binary being patched is a Windows .NET assembly, and VMware Workstation is required (not VMware Fusion or other hypervisors).

### Can I use VirtualBox instead of VMware?

Technically possible but not recommended or supported. VMware has better hypervisor hiding (`smbios.reflecthost`, `hypervisor.cpuid.v0`) and VirtualBox leaks more VM signatures that SEB can detect.

---

## Detection & Safety

### Will my teacher/school find out?

It depends on your school's SEB configuration:

| Scenario | Risk Level | Details |
|---|---|---|
| School does NOT collect SEB logs | Low | Server only sees "exam completed normally" |
| School asks students to submit logs | High | Logs contain `VMware Virtual Platform` and `integrity compromised` |
| School uses remote proctoring software | Medium | Proctoring software may detect VMware separately from SEB |

**Always clean logs before any submission:**
```bash
python tools/main.py logs --scan    # Preview
python tools/main.py logs           # Clean
```

Or manually delete: `%LOCALAPPDATA%\SafeExamBrowser\Logs\*`

### What does "Application integrity is compromised" mean?

This is a **warning, not a blocker**. SEB detects that `SafeExamBrowser.Monitoring.dll` has been modified (different file hash). Despite the warning, SEB continues to run normally. The warning is written to local logs only.

### Does the Moodle server see my VM detection?

The Moodle server receives a limited set of information:
- SEB version, session times, normal/abnormal exit status
- Configuration validation result (pass/fail)

It does **NOT** receive:
- Full local log files
- Specific VM detection details
- Process lists
- Integrity compromise details

However, SEB has an `IntegrityModule` that may send a "integrity failed" signal if Moodle is configured for server-side integrity checks.

### What if my school requires log submission?

**Do not submit patched logs.** Options:
1. Clean logs with `log_cleaner.py` before submission (removes VMware traces)
2. Delete logs entirely and claim "SEB crashed"
3. Use a clean SEB installation on a separate machine for submission

---

## Technical

### How does the patching work?

Two patchers modify `SafeExamBrowser.Monitoring.dll` using IL (Intermediate Language) manipulation:

1. **seb-patcher** (dnlib) — Rewrites `VirtualMachineDetector` methods to return `false`
2. **display-patcher** (Mono.Cecil) — Rewrites `DisplayMonitor.TryLoadDisplays()` to return a fake display and `ValidateConfiguration` to return `IsAllowed=true`

### Why does VMware cause "0 displays detected"?

SEB uses WMI (`WmiMonitorBasicDisplayParams`) to query monitor information. In VMware, WMI doesn't return display data properly, causing SEB to think there are 0 monitors. The display patcher bypasses this by hardcoding a fake internal display.

### Will this break SEB's exam functionality?

No. The patches only affect the monitoring/detection modules. SEB's core functionality (browser lockdown, screen recording, config validation) works normally.

### Do I need to patch again after Windows updates?

Possibly. Windows updates can sometimes overwrite DLLs in `Program Files`. Check if SEB still works after updates; if not, re-run the patchers.

### The DLL is locked / cannot be replaced

Common causes and fixes:

| Locked by | Fix |
|---|---|
| `SafeExamBrowser.Service.exe` | `net stop SafeExamBrowser.Service` |
| `SafeExamBrowser.exe` | `taskkill /f /im SafeExamBrowser*` |
| `dnSpy.exe` | `taskkill /f /im dnSpy*` |
| Windows service auto-restart | `taskkill /f /im SafeExamBrowser* && timeout /t 5` then replace |

### VM network is not working (DNS timeout)

Switch from NAT to Bridged mode:
1. VMware → Settings → Network Adapter
2. Change from NAT to **Bridged** (勾选 "Copy physical network connection state")
3. Restart VM

Or set DNS manually in the VM:
```cmd
netsh interface ip set dns "Ethernet0" static 114.114.114.114
```

### Shared folder path with spaces causes errors

CMD can't handle UNC paths with spaces. Map to a drive letter first:
```cmd
net use Z: "\\vmware-host\Shared Folders\seb-bypass"
Z:\force_replace.cmd
```

### VMware Tools installed but resolution is wrong

1. VMware menu: **View → Autosize → Adapt Guest**
2. Or manually: right-click desktop → Display Settings → match host resolution
3. Restart VM after installing VMware Tools

---

## Troubleshooting

### SEB shows "locked" screen (red screen)

SEB didn't shut down cleanly last time. Fix:
```powershell
taskkill /f /im SafeExamBrowser* 2>$null
Remove-Item "$env:APPDATA\SafeExamBrowser\SebClient.seb" -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\SafeExamBrowser\Cache\*" -Recurse -Force
```

### SEB installer stuck at "Processing: VC++ Runtime"

The VC++ installer runs silently and may show a hidden UAC dialog. Press `Alt+Tab` in the VM to check. Or pre-install VC++ from Microsoft's website first.

### PowerShell blocks script execution

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
```

Or run with bypass flag:
```powershell
powershell -ExecutionPolicy Bypass -File "script.ps1"
```

### "Face detection model could not be loaded" in VMware

**This is outside the scope of the VM and display patchers.** SEB v3.10.1 itself has no built-in face-detection module (`SafeExamBrowser.Proctoring.dll` only implements `ScreenProctoringImplementation` for periodic desktop screenshots). The `"Face detection model could not be loaded"` error comes from the **exam platform's browser-side JavaScript / WASM / WebGL proctoring** (such as face-api.js, TensorFlow.js, MediaPipe, or ONNX Runtime Web) running inside SEB's embedded Chromium browser (CEF).

Even if the Windows Camera app works (it uses UWP/MediaFoundation directly), browser-based face-detection models depend on **WebGL / WebGL2** and model asset downloads, which often fail in VMware when 3D acceleration is disabled. Also note that `seb-patcher` preserves `TryCalculateBrowserExamKey` and `TryCalculateAppSignatureKey` in `IntegrityModule` so `X-SafeExamBrowser-RequestHash` headers are not broken.

Troubleshooting steps inside the VM:
1. **Enable VMware 3D acceleration**: Shut down the VM, enable **VM Settings -> Display -> Accelerate 3D graphics** (or add `mks.enable3d = "TRUE"` to your `.vmx` file), and confirm VMware Tools SVGA 3D drivers are installed.
2. **Verify WebGL in Chrome/Edge**: Open regular Chrome or Edge inside the VM, visit `chrome://gpu`, and check that WebGL / WebGL2 are hardware-accelerated (or active) and that the exam platform's camera/model check passes there.
3. **Inspect SEB browser logs**: Check `%LOCALAPPDATA%\SafeExamBrowser\Logs\*_Browser.log` for `[INFO:CONSOLE]` errors (WebGL context creation failure, WASM errors, CORS, or failed model `.json`/`.bin`/`.wasm` requests).
4. **Check Windows camera privacy**: Ensure Windows Settings -> Privacy -> Camera allows desktop applications to access the camera.

### Running SEB over Windows Remote Desktop (RDP)

SEB v3.10.1 enforces several RDP-specific barriers across multiple assemblies, so patching only `SafeExamBrowser.Monitoring.dll` is not enough:

1. **`RemoteSessionDetector` (`SafeExamBrowser.Monitoring.dll`) & `RemoteSessionOperation` (`SafeExamBrowser.exe`)**: Detect `SystemInformation.TerminalServerSession` (`SM_REMOTESESSION`) and abort startup when `.seb` key `allowScreenSharing` is `false` (default).
2. **`WDA_EXCLUDEFROMCAPTURE` (`SafeExamBrowser.UserInterface.Shared.dll` / `SafeExamBrowser.Client.exe`)**: `WindowExtensions.ExcludeFromCapture` and `WindowGuardOperation` call `SetWindowDisplayAffinity(..., 17)`, causing SEB windows to appear **black or completely invisible** over RDP.
3. **`CreateNewDesktop` / `SwitchDesktop` (`SafeExamBrowser.exe`)**: `KioskModeOperation` defaults to `CreateNewDesktop` (`createNewDesktop = true`), creating an isolated desktop and launching `Client.exe` on it, which frequently fails or freezes inside an RDP session.
4. **Session-change lock screen (`SafeExamBrowser.Client.exe`)**: `MonitoringResponsibility.Sentinel_SessionChanged` triggers the red lock screen on `RemoteConnect` / `RemoteDisconnect` events when `disableSessionChangeLockScreen` is `false`.
5. **`fDenyTSConnections` in `SafeExamBrowser.Service`**: `RemoteConnectionConfiguration` sets `HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\fDenyTSConnections = 1` (which drops RDP connections), while `ServiceOperation` aborts if the service is stopped under `sebServicePolicy = Mandatory` and `sebServiceIgnore = false`.
6. **WMI display check (`SafeExamBrowser.Monitoring.dll`)**: `DisplayMonitor` WMI queries (`WmiMonitorBasicDisplayParams`) fail or return 0 monitors on RDP virtual display adapters.

**How the updated toolkit handles RDP:**
- `seb-patcher` patches `RemoteSessionDetector`, `RemoteSessionOperation`, `WindowExtensions.ExcludeFromCapture` / `WindowGuardOperation`, `KioskModeOperation` (avoiding `CreateNewDesktop` / `SwitchDesktop` failure in RDP sessions), `MonitoringResponsibility.Sentinel_SessionChanged`, and `ServiceOperation` / `RemoteConnectionConfiguration`.
- `display-patcher` patches `DisplayMonitor` without blocking on interactive key prompts.
- Always run `scripts\patch_all.cmd` as Administrator (which stops/disables `SafeExamBrowser.Service` and patches all required binaries together). Do **not** use standalone `Monitoring.dll`-only replacement scripts such as `force_replace.cmd`, as they leave `SafeExamBrowser.exe`, `SafeExamBrowser.Client.exe`, `SafeExamBrowser.Configuration.dll`, and `SafeExamBrowser.UserInterface.Shared.dll` unpatched.

---

## Support

### Where can I get help?

- **Free**: Open a [GitHub Issue](https://github.com/Tyleraltight/SafeExamBrowser_bypass/issues)
- **Priority**: Contact via email: [chuzihang456@gmail.com](mailto:chuzihang456@gmail.com) for step-by-step guidance

### I found a bug / SEB updated and patches are broken

Open a [GitHub Issue](https://github.com/Tyleraltight/SafeExamBrowser_bypass/issues/new) with:
1. Your SEB version (from SEB → About)
2. The exact error message
3. Your SEB runtime log (`%LOCALAPPDATA%\SafeExamBrowser\Logs\`)

---

*This tool is for educational and research purposes only. Use responsibly.*
