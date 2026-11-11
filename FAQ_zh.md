# 常见问题（FAQ）

**[English](FAQ.md) | [中文](FAQ_zh.md)**

## 基础问题

### 这个工具是什么？

一个在 VMware 虚拟机中运行 Safe Exam Browser（SEB）的工具包。通过补丁修改 SEB 的监控 DLL，绕过虚拟机检测和显示器验证，让你在虚拟机中运行 SEB，同时保持宿主机完全自由。

### 这个真的能用吗？

能。我们已在 SEB v3.10.1.864 + Moodle 环境下测试通过。补丁工具能禁用全部 7 个虚拟机检测方法，并解决 VMware 导致的"检测到 0 个显示器"错误。

### 支持哪些 SEB 版本？

目前确认适用于 **SEB v3.10.1 和 v3.10.2**。其他 v3.x 版本可能有效但未经测试。SEB v3.6.x 需要不同的补丁工具（参见 [nxvvvv/safe-exam-browser-bypass](https://github.com/nxvvvv/safe-exam-browser-bypass)）。

### 支持 macOS 或 Linux 吗？

不支持。本工具仅适用于 Windows。被补丁的 SEB 二进制文件是 Windows .NET 程序集，且需要 VMware Workstation（不支持 VMware Fusion 或其他虚拟化软件）。

### 可以用 VirtualBox 代替 VMware 吗？

技术上可以但不推荐，也不在支持范围内。VMware 的虚拟机隐藏功能更成熟（`smbios.reflecthost`、`hypervisor.cpuid.v0`），VirtualBox 泄漏更多虚拟机特征，容易被 SEB 检测到。

---

## 检测与安全

### 老师/学校会发现吗？

取决于你学校的 SEB 配置：

| 场景 | 风险等级 | 说明 |
|---|---|---|
| 学校不收集 SEB 日志 | 低 | 服务器只看到"考试正常完成" |
| 学校要求学生提交日志 | 高 | 日志包含 `VMware Virtual Platform` 和 `integrity compromised` |
| 学校使用远程监考软件 | 中 | 监考软件可能独立于 SEB 检测虚拟机 |

**提交日志前务必清理：**
```bash
python tools/main.py logs --scan    # 预览
python tools/main.py logs           # 清理
```

或手动删除：`%LOCALAPPDATA%\SafeExamBrowser\Logs\*`

### "Application integrity is compromised" 是什么意思？

这是一个**警告，不会阻止运行**。SEB 检测到 `SafeExamBrowser.Monitoring.dll` 被修改（文件哈希值不同）。尽管有这个警告，SEB 会正常继续运行。警告只写入本地日志。

### Moodle 服务器能看到虚拟机信息吗？

服务器收到的信息有限：
- SEB 版本、会话时间、正常/异常退出状态
- 配置验证结果（通过/失败）

服务器**不会**收到：
- 完整的本地日志文件
- 具体的虚拟机检测详情
- 进程列表
- 完整性失败详情

但 SEB 有一个 `IntegrityModule`，如果 Moodle 配置了服务器端完整性校验，可能会发送"完整性失败"信号。

### 如果学校要求提交日志怎么办？

**不要提交补丁后的日志。** 可选方案：
1. 提交前用 `log_cleaner.py` 清理日志（去除 VMware 痕迹）
2. 直接删除日志，声称"SEB 崩溃了"
3. 在另一台干净的机器上用未修改的 SEB 提交

---

## 技术问题

### 补丁是怎么工作的？

两个补丁工具使用 IL（中间语言）操作修改 `SafeExamBrowser.Monitoring.dll`：

1. **seb-patcher**（dnlib）— 重写 `VirtualMachineDetector` 方法，使其返回 `false`
2. **display-patcher**（Mono.Cecil）— 重写 `DisplayMonitor.TryLoadDisplays()` 返回伪造的显示器，`ValidateConfiguration` 返回 `IsAllowed=true`

### 为什么 VMware 会导致"检测到 0 个显示器"？

SEB 使用 WMI（`WmiMonitorBasicDisplayParams`）查询显示器信息。在 VMware 中 WMI 无法正确返回显示数据，导致 SEB 认为有 0 个显示器。显示器补丁通过硬编码一个伪造的内部显示器来绕过这个问题。

### 补丁会影响 SEB 的考试功能吗？

不会。补丁只影响监控/检测模块。SEB 的核心功能（浏览器锁定、屏幕录制、配置验证）正常工作。

### Windows 更新后需要重新补丁吗？

可能需要。Windows 更新有时会覆盖 `Program Files` 中的 DLL。更新后检查 SEB 是否还能正常工作，如果不行就重新运行补丁工具。

### DLL 被锁定 / 无法替换

常见原因和解决方法：

| 锁定者 | 解决方法 |
|---|---|
| `SafeExamBrowser.Service.exe` | `net stop SafeExamBrowser.Service` |
| `SafeExamBrowser.exe` | `taskkill /f /im SafeExamBrowser*` |
| `dnSpy.exe` | `taskkill /f /im dnSpy*` |
| Windows 服务自动重启 | `taskkill /f /im SafeExamBrowser* && timeout /t 5` 再替换 |

### 虚拟机网络不通（DNS 超时）

从 NAT 模式切换到桥接模式：
1. VMware → 设置 → 网络适配器
2. 从 NAT 改为**桥接模式**（勾选"复制物理网络连接状态"）
3. 重启虚拟机

或在虚拟机中手动设置 DNS：
```cmd
netsh interface ip set dns "Ethernet0" static 114.114.114.114
```

### 共享文件夹路径有空格导致报错

CMD 无法正确处理 UNC 路径中的空格。先映射为盘符：
```cmd
net use Z: "\\vmware-host\Shared Folders\seb-bypass"
Z:\force_replace.cmd
```

### VMware Tools 已安装但分辨率不对

1. VMware 菜单栏：**查看 → 自动调整大小 → 立即适应客户机**
2. 或手动设置：桌面右键 → 显示设置 → 设置与宿主机一致的分辨率
3. 安装 VMware Tools 后重启虚拟机

---

## 故障排查

### SEB 显示红色"已锁定"界面

SEB 上次没有正常关闭。修复：
```powershell
taskkill /f /im SafeExamBrowser* 2>$null
Remove-Item "$env:APPDATA\SafeExamBrowser\SebClient.seb" -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\SafeExamBrowser\Cache\*" -Recurse -Force
```

### SEB 安装器卡在 "Processing: VC++ Runtime"

VC++ 安装器在后台静默运行，可能弹出被遮挡的 UAC 对话框。在虚拟机中按 `Alt+Tab` 检查。或先从微软官网手动安装 VC++。

### PowerShell 阻止脚本运行

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
```

或使用绕过参数运行：
```powershell
powershell -ExecutionPolicy Bypass -File "script.ps1"
```

### VMware 中提示 "Face detection model could not be loaded"（人脸检测模型无法加载）

**此问题超出虚拟机与显示器补丁的作用范围。** SEB v3.10.1 本身不包含任何人脸检测模块（`SafeExamBrowser.Proctoring.dll` 仅实现了用于定时桌面截图的 `ScreenProctoringImplementation`）。`"Face detection model could not be loaded"` 报错来自**考试平台自身在浏览器端运行的 JavaScript / WASM / WebGL 监考脚本**（例如 face-api.js、TensorFlow.js、MediaPipe 或 ONNX Runtime Web），运行在 SEB 内嵌的 Chromium 浏览器（CEF）中。

即使 Windows 自带的"相机"应用可以正常预览（它直接使用 UWP/MediaFoundation 接口），浏览器端的人脸检测模型仍依赖 **WebGL / WebGL2** 与模型文件加载；在 VMware 中未开启 3D 加速时极易失败。另外，新版 `seb-patcher` 已保留 `IntegrityModule` 中的 `TryCalculateBrowserExamKey` 与 `TryCalculateAppSignatureKey` 原样逻辑，避免破坏 `X-SafeExamBrowser-RequestHash` 请求头。

虚拟机内排查步骤：
1. **开启 VMware 3D 图形加速**：关闭虚拟机后，在 **虚拟机设置 -> 显示器** 中勾选 **加速 3D 图形**（或在 `.vmx` 中配置 `mks.enable3d = "TRUE"`），并确认已安装 VMware Tools SVGA 3D 驱动。
2. **在普通 Chrome/Edge 中测试 WebGL**：在虚拟机内打开常规 Chrome 或 Edge，访问 `chrome://gpu` 查看 WebGL / WebGL2 状态，并测试考试平台的摄像头/模型自检是否可以通过。
3. **查看 SEB 浏览器日志**：检查 `%LOCALAPPDATA%\SafeExamBrowser\Logs\*_Browser.log` 中的 `[INFO:CONSOLE]` 日志，确认具体失败原因（如 WebGL 上下文创建失败、WASM 编译异常、CORS 或模型 `.json`/`.bin`/`.wasm` 请求失败）。
4. **检查 Windows 相机权限**：确认 Windows 设置 -> 隐私 -> 相机 中已允许桌面应用访问摄像头。

### 通过 Windows 远程桌面（RDP）运行 SEB

SEB v3.10.1 在多个程序集中设置了针对 RDP 的限制，仅修改 `SafeExamBrowser.Monitoring.dll` 无法正常工作：

1. **`RemoteSessionDetector`（`SafeExamBrowser.Monitoring.dll`）与 `RemoteSessionOperation`（`SafeExamBrowser.exe`）**：通过 `SystemInformation.TerminalServerSession`（`SM_REMOTESESSION`）检测远程会话；当 `.seb` 配置中的 `allowScreenSharing` 为 `false`（默认值）时直接中止启动。
2. **`WDA_EXCLUDEFROMCAPTURE`（`SafeExamBrowser.UserInterface.Shared.dll` / `SafeExamBrowser.Client.exe`）**：`WindowExtensions.ExcludeFromCapture` 与 `WindowGuardOperation` 会调用 `SetWindowDisplayAffinity(..., 17)`，导致 SEB 窗口在 RDP 画面中显示为**全黑或完全不可见**。
3. **`CreateNewDesktop` / `SwitchDesktop`（`SafeExamBrowser.exe`）**：`KioskModeOperation` 默认启用 `CreateNewDesktop`（`createNewDesktop = true`），会创建独立桌面并切换过去启动 `Client.exe`，这在 RDP 会话中极易失败、卡死或断开。
4. **会话切换锁屏（`SafeExamBrowser.Client.exe`）**：当 `disableSessionChangeLockScreen` 为 `false` 时，`MonitoringResponsibility.Sentinel_SessionChanged` 会在 `RemoteConnect` / `RemoteDisconnect` 等会话事件发生时触发红色锁屏界面。
5. **`SafeExamBrowser.Service` 修改 `fDenyTSConnections`**：`RemoteConnectionConfiguration` 会将 `HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\fDenyTSConnections` 设为 `1`（直接断开并禁用 RDP）；而当 `.seb` 中 `sebServicePolicy = Mandatory` 且 `sebServiceIgnore = false` 时，停用服务又会导致 `ServiceOperation` 中止 SEB。
6. **WMI 显示器检测（`SafeExamBrowser.Monitoring.dll`）**：`DisplayMonitor` 的 `WmiMonitorBasicDisplayParams` 查询在 RDP 虚拟显示适配器下会失败或返回 0 个显示器。

**新版补丁的应对方式：**
- `seb-patcher` 同步处理 `RemoteSessionDetector`、`RemoteSessionOperation`、`WindowExtensions.ExcludeFromCapture` / `WindowGuardOperation`、`KioskModeOperation`（避免在 RDP 会话中因 `CreateNewDesktop` / `SwitchDesktop` 失败）、`MonitoringResponsibility.Sentinel_SessionChanged` 以及 `ServiceOperation` / `RemoteConnectionConfiguration`。
- `display-patcher` 已移除阻塞非交互/RDP 运行的 `Console.ReadKey()` 等待。
- 请务必以管理员身份运行 `scripts\patch_all.cmd`（会自动停止并禁用 `SafeExamBrowser.Service`，并对全部所需程序集打补丁并校验）。切勿单独使用只替换 `SafeExamBrowser.Monitoring.dll` 的脚本（如 `force_replace.cmd`），否则会导致 `SafeExamBrowser.exe`、`SafeExamBrowser.Client.exe`、`SafeExamBrowser.Configuration.dll` 和 `SafeExamBrowser.UserInterface.Shared.dll` 保持未补丁状态。

---

## 支持

### 在哪里获取帮助？

- **免费**：在 [GitHub Issues](https://github.com/Tyleraltight/SafeExamBrowser_bypass/issues) 中提问
- **优先**：通过邮件联系 [chuzihang456@gmail.com](mailto:chuzihang456@gmail.com) 获取一对一指导

### 发现了 Bug / SEB 更新后补丁失效了

在 [GitHub Issues](https://github.com/Tyleraltight/SafeExamBrowser_bypass/issues/new) 中提交，包含：
1. 你的 SEB 版本（SEB → 关于）
2. 完整的错误信息
3. SEB 运行日志（`%LOCALAPPDATA%\SafeExamBrowser\Logs\`）

---

*本工具仅供教育和研究用途。请负责任地使用。*
