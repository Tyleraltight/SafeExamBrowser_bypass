using dnlib.DotNet;
using dnlib.DotNet.Emit;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace SebPatcher
{
    class Program
    {
        const string DefaultSebPath = @"C:\Program Files\SafeExamBrowser\Application";
        const int OperationResultSuccess = 3;

        static int Main(string[] args)
        {
            Console.OutputEncoding = System.Text.Encoding.UTF8;
            PrintBanner();

            if (args.Length < 1)
            {
                PrintUsage();
                return 1;
            }

            var command = args[0].ToLowerInvariant();

            try
            {
                switch (command)
                {
                    case "patch":
                        return Patch(args);
                    case "restore":
                        return Restore(args);
                    case "check":
                        return Check(args);
                    default:
                        Console.WriteLine($"[!] Unknown command: {command}");
                        PrintUsage();
                        return 1;
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"\n[!] Error: {ex.Message}");
                Console.ResetColor();
                return 1;
            }
        }

        static string ParseSebPath(string[] args)
        {
            for (int i = 1; i < args.Length; i++)
            {
                var arg = args[i];
                if (arg == "--path" || arg == "-p")
                {
                    if (i + 1 >= args.Length || args[i + 1].StartsWith("-", StringComparison.Ordinal))
                        throw new ArgumentException($"Missing directory value after {arg}");
                    return args[i + 1].Trim('"');
                }
                if (arg.StartsWith("--path=", StringComparison.OrdinalIgnoreCase))
                {
                    var val = arg.Substring("--path=".Length).Trim('"');
                    if (string.IsNullOrWhiteSpace(val))
                        throw new ArgumentException("Missing directory value in --path=");
                    return val;
                }
                if (!arg.StartsWith("-", StringComparison.Ordinal))
                    return arg.Trim('"');
            }
            return DefaultSebPath;
        }

        static void WriteModuleSafely(ModuleDefMD module, string targetPath)
        {
            var tempPath = targetPath + ".tmp";
            try
            {
                module.Write(tempPath);
                if (File.Exists(targetPath))
                    File.Replace(tempPath, targetPath, null);
                else
                    File.Move(tempPath, targetPath);
            }
            finally
            {
                if (File.Exists(tempPath))
                {
                    try { File.Delete(tempPath); } catch { }
                }
            }
        }

        static string ResolveLockdownPath(string sebPath)
        {
            var inApp = Path.Combine(sebPath, "SafeExamBrowser.Lockdown.dll");
            if (File.Exists(inApp))
                return inApp;

            var trimmed = sebPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            var parent = Directory.GetParent(trimmed)?.FullName;
            if (!string.IsNullOrEmpty(parent))
            {
                var inService = Path.Combine(parent, "Service", "SafeExamBrowser.Lockdown.dll");
                if (File.Exists(inService))
                    return inService;
            }

            return null;
        }

        static void CreateBackupIfMissing(string filePath)
        {
            var backupPath = filePath + ".bak";
            if (!File.Exists(backupPath))
            {
                File.Copy(filePath, backupPath, false);
                Console.WriteLine($"[+] Backup created: {backupPath}");
            }
            else
            {
                Console.WriteLine($"[*] Backup already exists: {backupPath}");
            }
        }

        static ModuleDefMD LoadModule(string filePath)
        {
            var ctx = new ModuleContext();
            var bytes = File.ReadAllBytes(filePath);
            var module = ModuleDefMD.Load(bytes, ctx);
            module.Context = ctx;
            return module;
        }

        static int Patch(string[] args)
        {
            var sebPath = ParseSebPath(args);
            if (!PatchMonitoring(sebPath))
                return 1;

            PatchConfiguration(sebPath);
            PatchUiShared(sebPath);
            PatchClient(sebPath);
            PatchRuntime(sebPath);
            PatchLockdown(sebPath);
            return 0;
        }

        static bool TryPrepareAssembly(string filePath, string label, out ModuleDefMD module)
        {
            module = null;
            if (!File.Exists(filePath))
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"\n[!] {label} not found at: {filePath}");
                Console.ResetColor();
                return false;
            }
            Console.WriteLine($"\n[*] Patching {label}...");
            CreateBackupIfMissing(filePath);
            module = LoadModule(filePath);
            return true;
        }

        static void WritePatchedStage(ModuleDefMD module, string filePath, int count, string label)
        {
            if (count > 0)
            {
                WriteModuleSafely(module, filePath);
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine($"[+] Patched {count} method(s) in {label}!");
                Console.ResetColor();
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"[!] No methods were patched in {label}!");
                Console.ResetColor();
            }
        }

        static int ResolveOperationResultSuccess(ModuleDefMD module)
        {
            var opResultType = module.GetTypes().FirstOrDefault(t => t.IsEnum && t.Name == "OperationResult");
            var successField = opResultType?.Fields.FirstOrDefault(f => f.IsLiteral && f.Name == "Success" && f.Constant != null);
            return successField != null ? Convert.ToInt32(successField.Constant.Value) : OperationResultSuccess;
        }

        static bool PatchMonitoring(string sebPath)
        {
            var dllPath = Path.Combine(sebPath, "SafeExamBrowser.Monitoring.dll");
            if (!File.Exists(dllPath))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[!] DLL not found: {dllPath}");
                Console.ResetColor();
                return false;
            }

            CreateBackupIfMissing(dllPath);
            var module = LoadModule(dllPath);
            Console.WriteLine($"[+] Loaded: {module.Assembly?.FullName ?? module.Name}");

            var vmMethods = new[]
            {
                "IsVirtualMachine", "HasNoSystemHardware", "HasVirtualDevice",
                "HasVirtualMacAddress", "IsVirtualCpu", "IsVirtualRegistry",
                "IsVirtualSystem", "HasLocalVirtualMachineDeviceCache"
            };
            var remoteSessionMethods = new[] { "IsRemoteSession", "IsWindowsRemoteDesktopSession", "IsWtsSession" };
            var patchedCount = 0;

            var vmDetectorType = module.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Monitoring.VirtualMachineDetector");
            if (vmDetectorType == null)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[!] VirtualMachineDetector type not found!");
                Console.ResetColor();
            }
            else
            {
                Console.WriteLine($"[+] Found type: {vmDetectorType.FullName}");
                foreach (var method in vmDetectorType.Methods.Where(m => m.HasBody && Array.Exists(vmMethods, name => name == m.Name)))
                {
                    PatchReturnFalse(method);
                    LogPatched(method.Name, "returns false");
                    patchedCount++;
                }
            }

            var remoteSessionType = module.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Monitoring.RemoteSessionDetector");
            if (remoteSessionType != null)
            {
                Console.WriteLine($"[+] Found type: {remoteSessionType.FullName}");
                foreach (var method in remoteSessionType.Methods.Where(m => m.HasBody && Array.Exists(remoteSessionMethods, name => name == m.Name)))
                {
                    PatchReturnFalse(method);
                    LogPatched($"(Remote) {method.Name}", "returns false");
                    patchedCount++;
                }
            }

            var appMonitorType = module.GetTypes().FirstOrDefault(t => t.Name == "ApplicationMonitor");
            if (appMonitorType != null)
            {
                Console.WriteLine($"[+] Found type: {appMonitorType.FullName}");
                var killHandlers = new[] { "SystemEvent_WindowChanged", "Timer_Elapsed", "HandleInstanceStart", "HandleExplorerStart" };
                foreach (var method in appMonitorType.Methods.Where(m =>
                    m.HasBody && !m.IsConstructor && m.ReturnType.FullName == "System.Void" &&
                    Array.Exists(killHandlers, name => name == m.Name)))
                {
                    PatchReturnVoid(method);
                    LogPatched($"(AppMonitor) {method.Name}", "void nop");
                    patchedCount++;
                }
            }

            if (patchedCount == 0)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[!] No methods were patched in Monitoring.dll!");
                Console.ResetColor();
                return false;
            }

            WritePatchedStage(module, dllPath, patchedCount, "SafeExamBrowser.Monitoring.dll");
            return true;
        }

        static void PatchConfiguration(string sebPath)
        {
            var configDllPath = Path.Combine(sebPath, "SafeExamBrowser.Configuration.dll");
            if (!TryPrepareAssembly(configDllPath, "SafeExamBrowser.Configuration.dll", out var configModule))
                return;

            var integrityPatchCount = 0;
            var integrityType = configModule.GetTypes().FirstOrDefault(
                t => t.FullName == "SafeExamBrowser.Configuration.Integrity.IntegrityModule");

            if (integrityType != null)
            {
                Console.WriteLine($"[+] Found type: {integrityType.FullName}");
                foreach (var method in integrityType.Methods.Where(m => m.HasBody))
                {
                    if (method.Name == "TryVerifyCodeSignature" || method.Name == "TryVerifySessionIntegrity")
                    {
                        if (PatchIntegrityOutBoolTrue(method))
                        {
                            LogPatched($"(Integrity) {method.Name}", "sets out isValid=true, returns true");
                            integrityPatchCount++;
                        }
                    }
                    else if (method.Name == "IsVirtualMachine" && method.ReturnType.FullName == "System.Boolean")
                    {
                        PatchOutParamsAndReturnFalse(method);
                        LogPatched($"(Integrity) {method.Name}", "clears out params, returns false");
                        integrityPatchCount++;
                    }
                    else if (method.Name == "TryCalculateBrowserExamKey" ||
                             method.Name == "TryCalculateAppSignatureKey" ||
                             method.Name == "TryReadSessionCache" ||
                             method.Name == "TryWriteSessionCache")
                    {
                        Console.WriteLine($"  [=] Preserved (untouched): {method.Name}");
                    }
                }
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[!] IntegrityModule type not found in Configuration.dll");
                Console.ResetColor();
            }

            WritePatchedStage(configModule, configDllPath, integrityPatchCount, "SafeExamBrowser.Configuration.dll");
        }

        static void PatchUiShared(string sebPath)
        {
            var uiSharedPath = Path.Combine(sebPath, "SafeExamBrowser.UserInterface.Shared.dll");
            if (!TryPrepareAssembly(uiSharedPath, "SafeExamBrowser.UserInterface.Shared.dll", out var uiModule))
                return;

            var uiPatchCount = 0;
            var winExtType = uiModule.GetTypes().FirstOrDefault(
                t => t.FullName == "SafeExamBrowser.UserInterface.Shared.Utilities.WindowExtensions");
            if (winExtType != null)
            {
                Console.WriteLine($"[+] Found type: {winExtType.FullName}");
                var excludeMethod = winExtType.Methods.FirstOrDefault(
                    m => m.Name == "ExcludeFromCapture" && m.HasBody && m.ReturnType.FullName == "System.Boolean");
                if (excludeMethod != null)
                {
                    // Skip SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) so windows remain visible over RDP.
                    PatchReturnTrue(excludeMethod);
                    LogPatched("(UI) ExcludeFromCapture", "returns true (skips SetWindowDisplayAffinity)");
                    uiPatchCount++;
                }
            }

            WritePatchedStage(uiModule, uiSharedPath, uiPatchCount, "SafeExamBrowser.UserInterface.Shared.dll");
        }

        static void PatchClient(string sebPath)
        {
            var clientPath = Path.Combine(sebPath, "SafeExamBrowser.Client.exe");
            if (!TryPrepareAssembly(clientPath, "SafeExamBrowser.Client.exe", out var clientModule))
                return;

            var opSuccess = ResolveOperationResultSuccess(clientModule);
            var clientPatchCount = 0;

            foreach (var type in clientModule.GetTypes())
            {
                if (type.Name == "IntegrityResponsibility" || type.FullName.Contains("IntegrityResponsibility"))
                {
                    Console.WriteLine($"[+] Found type: {type.FullName}");
                    foreach (var method in type.Methods.Where(m => m.HasBody && !m.IsConstructor && m.ReturnType.FullName == "System.Void"))
                    {
                        bool shouldPatch = method.Name.Contains("Integrity") ||
                                           method.Name.Contains("Schedule") ||
                                           method.Name.Contains("Verify") ||
                                           method.Name.StartsWith("<");
                        if (shouldPatch)
                        {
                            PatchReturnVoid(method);
                            LogPatched($"(Client Integrity) {method.Name}", "void nop");
                            clientPatchCount++;
                        }
                    }
                }

                if (type.Name == "MonitoringResponsibility" || type.FullName.Contains("MonitoringResponsibility"))
                {
                    Console.WriteLine($"[+] Found type: {type.FullName}");
                    foreach (var method in type.Methods.Where(m => m.HasBody && !m.IsConstructor && m.ReturnType.FullName == "System.Void"))
                    {
                        bool isSentinel = method.Name.Contains("Sentinel_") ||
                                          method.Name.Contains("DisplayMonitor_") ||
                                          method.Name.Contains("ApplicationMonitor_") ||
                                          method.Name.StartsWith("<");
                        if (isSentinel)
                        {
                            PatchReturnVoid(method);
                            LogPatched($"(Client Monitoring) {method.Name}", "void nop");
                            clientPatchCount++;
                        }
                    }
                }

                if (type.FullName == "SafeExamBrowser.Client.Operations.WindowGuardOperation")
                {
                    Console.WriteLine($"[+] Found type: {type.FullName}");
                    var performMethod = type.Methods.FirstOrDefault(
                        m => m.Name == "Perform" && m.HasBody && m.ReturnType.FullName.Contains("OperationResult"));
                    if (performMethod != null)
                    {
                        PatchReturnInt(performMethod, opSuccess);
                        LogPatched("(Client WindowGuard) Perform", "OperationResult.Success");
                        clientPatchCount++;
                    }
                }
            }

            WritePatchedStage(clientModule, clientPath, clientPatchCount, "SafeExamBrowser.Client.exe");
        }

        static void PatchRuntime(string sebPath)
        {
            var runtimePath = Path.Combine(sebPath, "SafeExamBrowser.exe");
            if (!TryPrepareAssembly(runtimePath, "SafeExamBrowser.exe", out var rtModule))
                return;

            var opSuccess = ResolveOperationResultSuccess(rtModule);
            var rtPatchCount = 0;
            var targetOps = new[]
            {
                "ApplicationIntegrityOperation",
                "SessionIntegrityOperation",
                "VirtualMachineOperation",
                "RemoteSessionOperation"
            };

            foreach (var type in rtModule.GetTypes())
            {
                if (Array.Exists(targetOps, t => type.Name == t))
                {
                    Console.WriteLine($"[+] Found type: {type.FullName}");
                    foreach (var method in type.Methods.Where(m => m.HasBody && !m.IsConstructor))
                    {
                        bool isOpMethod = method.Name == "Perform" ||
                                          method.Name == "Repeat" ||
                                          method.Name == "Revert" ||
                                          method.Name == "ValidatePolicy";

                        if (isOpMethod && method.ReturnType.FullName.Contains("OperationResult"))
                        {
                            PatchReturnInt(method, opSuccess);
                            LogPatched($"(Runtime) {type.Name}.{method.Name}", "OperationResult.Success");
                            rtPatchCount++;
                        }
                        else if (method.ReturnType.FullName == "System.Boolean" &&
                                 (method.Name.Contains("Verify") || method.Name.Contains("Initialize") ||
                                  method.Name.Contains("Validate")))
                        {
                            PatchReturnTrue(method);
                            LogPatched($"(Runtime) {type.Name}.{method.Name}", "return true");
                            rtPatchCount++;
                        }
                        else if (method.ReturnType.FullName == "System.Void" &&
                                 (method.Name.Contains("Verify") || method.Name.Contains("Finalize") ||
                                  method.Name.Contains("Log")) &&
                                 !method.Name.StartsWith("add_") && !method.Name.StartsWith("remove_"))
                        {
                            PatchReturnVoid(method);
                            LogPatched($"(Runtime) {type.Name}.{method.Name}", "void nop");
                            rtPatchCount++;
                        }
                    }
                }
                else if (type.FullName == "SafeExamBrowser.Runtime.Operations.Session.ServiceOperation")
                {
                    Console.WriteLine($"[+] Found type: {type.FullName}");
                    foreach (var method in type.Methods.Where(m =>
                        m.HasBody && (m.Name == "Perform" || m.Name == "Repeat") && m.ReturnType.FullName.Contains("OperationResult")))
                    {
                        PatchReturnInt(method, opSuccess);
                        LogPatched($"(Runtime) ServiceOperation.{method.Name}", "OperationResult.Success");
                        rtPatchCount++;
                    }
                }
                else if (type.FullName == "SafeExamBrowser.Runtime.Operations.Session.KioskModeOperation")
                {
                    Console.WriteLine($"[+] Found type: {type.FullName}");
                    var createCustomDesktop = type.Methods.FirstOrDefault(
                        m => m.Name == "CreateCustomDesktop" && m.HasBody && m.ReturnType.FullName == "System.Void");
                    if (createCustomDesktop != null)
                    {
                        if (PatchKioskCreateCustomDesktop(rtModule, createCustomDesktop))
                            LogPatched("(Runtime) KioskModeOperation.CreateCustomDesktop", "skip when TerminalServerSession is true");
                        else
                            Console.WriteLine("  [=] KioskModeOperation.CreateCustomDesktop already patched");
                        rtPatchCount++;
                    }
                }
            }

            WritePatchedStage(rtModule, runtimePath, rtPatchCount, "SafeExamBrowser.exe");
        }

        static void PatchLockdown(string sebPath)
        {
            var lockdownPath = ResolveLockdownPath(sebPath);
            if (lockdownPath == null)
            {
                Console.WriteLine("\n[*] SafeExamBrowser.Lockdown.dll not found in Application/ or ../Service/ (skipping).");
                return;
            }

            if (!TryPrepareAssembly(lockdownPath, $"SafeExamBrowser.Lockdown.dll ({lockdownPath})", out var ldModule))
                return;

            var ldPatchCount = 0;
            var remoteConnCfg = ldModule.GetTypes().FirstOrDefault(
                t => t.FullName == "SafeExamBrowser.Lockdown.FeatureConfigurations.RegistryConfigurations.MachineHive.RemoteConnectionConfiguration");
            var regConfigItemType = ldModule.GetTypes().FirstOrDefault(
                t => t.FullName == "SafeExamBrowser.Lockdown.FeatureConfigurations.RegistryConfigurations.RegistryConfigurationItem");

            if (remoteConnCfg != null && regConfigItemType != null)
            {
                Console.WriteLine($"[+] Found type: {remoteConnCfg.FullName}");
                var getItems = remoteConnCfg.Methods.FirstOrDefault(m => m.Name == "get_Items" && m.HasBody);
                if (getItems != null)
                {
                    PatchReturnEmptyArray(getItems, regConfigItemType);
                    LogPatched("(Lockdown) RemoteConnectionConfiguration.get_Items", "empty RegistryConfigurationItem[0] (preserves fDenyTSConnections)");
                    ldPatchCount++;
                }
            }

            WritePatchedStage(ldModule, lockdownPath, ldPatchCount, "SafeExamBrowser.Lockdown.dll");
        }

        static void LogPatched(string name, string detail)
        {
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine($"  [+] Patched {name} -> {detail}");
            Console.ResetColor();
        }

        static void ResetBody(MethodDef method)
        {
            method.Body.Instructions.Clear();
            method.Body.ExceptionHandlers.Clear();
            method.Body.Variables.Clear();
            method.Body.InitLocals = false;
            method.Body.KeepOldMaxStack = false;
        }

        static void ReplaceBody(MethodDef method, params Instruction[] instructions)
        {
            ResetBody(method);
            foreach (var instr in instructions)
                method.Body.Instructions.Add(instr);
        }

        static void PatchReturnFalse(MethodDef method) =>
            ReplaceBody(method, OpCodes.Ldc_I4_0.ToInstruction(), OpCodes.Ret.ToInstruction());

        static void PatchReturnTrue(MethodDef method) =>
            ReplaceBody(method, OpCodes.Ldc_I4_1.ToInstruction(), OpCodes.Ret.ToInstruction());

        static void PatchReturnVoid(MethodDef method) =>
            ReplaceBody(method, OpCodes.Ret.ToInstruction());

        static void PatchReturnInt(MethodDef method, int value) =>
            ReplaceBody(method, OpCodes.Ldc_I4.ToInstruction(value), OpCodes.Ret.ToInstruction());

        static bool PatchIntegrityOutBoolTrue(MethodDef method)
        {
            var outParam = method.Parameters.FirstOrDefault(
                p => p.IsNormalMethodParameter && p.Type.FullName == "System.Boolean&");
            if (outParam == null)
                return false;

            ReplaceBody(
                method,
                Instruction.Create(OpCodes.Ldarg, outParam),
                OpCodes.Ldc_I4_1.ToInstruction(),
                OpCodes.Stind_I1.ToInstruction(),
                OpCodes.Ldc_I4_1.ToInstruction(),
                OpCodes.Ret.ToInstruction());
            return true;
        }

        static void PatchOutParamsAndReturnFalse(MethodDef method)
        {
            var outParams = method.Parameters
                .Where(p => p.IsNormalMethodParameter && p.Type.IsByRef)
                .ToList();

            ResetBody(method);

            foreach (var p in outParams)
            {
                var elemFullName = p.Type.Next?.FullName;
                method.Body.Instructions.Add(Instruction.Create(OpCodes.Ldarg, p));
                if (elemFullName == "System.Int32")
                {
                    method.Body.Instructions.Add(OpCodes.Ldc_I4_0.ToInstruction());
                    method.Body.Instructions.Add(OpCodes.Stind_I4.ToInstruction());
                }
                else if (elemFullName == "System.Double")
                {
                    method.Body.Instructions.Add(OpCodes.Ldc_R8.ToInstruction(0.0));
                    method.Body.Instructions.Add(OpCodes.Stind_R8.ToInstruction());
                }
                else if (elemFullName == "System.Boolean")
                {
                    method.Body.Instructions.Add(OpCodes.Ldc_I4_0.ToInstruction());
                    method.Body.Instructions.Add(OpCodes.Stind_I1.ToInstruction());
                }
                else
                {
                    method.Body.Instructions.Add(OpCodes.Ldnull.ToInstruction());
                    method.Body.Instructions.Add(OpCodes.Stind_Ref.ToInstruction());
                }
            }

            method.Body.Instructions.Add(OpCodes.Ldc_I4_0.ToInstruction());
            method.Body.Instructions.Add(OpCodes.Ret.ToInstruction());
        }

        static bool IsKioskCreateCustomDesktopPatched(MethodDef method)
        {
            var instrs = method.Body.Instructions;
            return instrs.Count >= 3 &&
                   instrs[0].OpCode == OpCodes.Call &&
                   (instrs[0].Operand?.ToString()?.Contains("get_TerminalServerSession") ?? false) &&
                   (instrs[1].OpCode == OpCodes.Brfalse || instrs[1].OpCode == OpCodes.Brfalse_S) &&
                   instrs[2].OpCode == OpCodes.Ret;
        }

        static bool PatchKioskCreateCustomDesktop(ModuleDefMD rtModule, MethodDef method)
        {
            if (IsKioskCreateCustomDesktopPatched(method))
                return false;

            var winFormsRef = rtModule.GetAssemblyRef("System.Windows.Forms")
                ?? new AssemblyRefUser("System.Windows.Forms", new Version(4, 0, 0, 0), new PublicKeyToken("b77a5c561934e089"));
            var sysInfoRef = new TypeRefUser(rtModule, "System.Windows.Forms", "SystemInformation", winFormsRef);
            var getTerminalServerSessionRef = new MemberRefUser(
                rtModule,
                "get_TerminalServerSession",
                MethodSig.CreateStatic(rtModule.CorLibTypes.Boolean),
                sysInfoRef);

            var firstOriginal = method.Body.Instructions[0];
            method.Body.KeepOldMaxStack = false;
            method.Body.Instructions.Insert(0, Instruction.Create(OpCodes.Call, getTerminalServerSessionRef));
            method.Body.Instructions.Insert(1, Instruction.Create(OpCodes.Brfalse, firstOriginal));
            method.Body.Instructions.Insert(2, OpCodes.Ret.ToInstruction());
            return true;
        }

        static void PatchReturnEmptyArray(MethodDef method, ITypeDefOrRef elementType) =>
            ReplaceBody(
                method,
                OpCodes.Ldc_I4_0.ToInstruction(),
                Instruction.Create(OpCodes.Newarr, elementType),
                OpCodes.Ret.ToInstruction());

        static int Restore(string[] args)
        {
            var sebPath = ParseSebPath(args);
            var files = new List<string>
            {
                Path.Combine(sebPath, "SafeExamBrowser.Monitoring.dll"),
                Path.Combine(sebPath, "SafeExamBrowser.Configuration.dll"),
                Path.Combine(sebPath, "SafeExamBrowser.UserInterface.Shared.dll"),
                Path.Combine(sebPath, "SafeExamBrowser.Client.exe"),
                Path.Combine(sebPath, "SafeExamBrowser.exe")
            };

            var lockdownPath = ResolveLockdownPath(sebPath);
            if (lockdownPath != null)
                files.Add(lockdownPath);

            int restored = 0;
            int missing = 0;

            foreach (var filePath in files)
            {
                var backupPath = filePath + ".bak";
                if (File.Exists(backupPath))
                {
                    File.Copy(backupPath, filePath, true);
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine($"[+] Restored: {filePath}");
                    Console.ResetColor();
                    restored++;
                }
                else
                {
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine($"[-] No backup found: {backupPath}");
                    Console.ResetColor();
                    missing++;
                }
            }

            if (restored == 0)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[!] No backup files were found to restore.");
                Console.ResetColor();
                return 1;
            }

            Console.WriteLine($"\n[+] Restore complete: {restored} restored, {missing} without backup.");
            return 0;
        }

        static int Check(string[] args)
        {
            var sebPath = ParseSebPath(args);
            bool allOk = true;

            // 1. SafeExamBrowser.Monitoring.dll
            var monitoringPath = Path.Combine(sebPath, "SafeExamBrowser.Monitoring.dll");
            if (!File.Exists(monitoringPath))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[!] Missing: {monitoringPath}");
                Console.ResetColor();
                return 1;
            }

            allOk &= CheckAssemblyHeader(monitoringPath);
            var monModule = LoadModule(monitoringPath);
            var vmTargets = new[]
            {
                "IsVirtualMachine", "HasNoSystemHardware", "HasVirtualDevice",
                "HasVirtualMacAddress", "IsVirtualCpu", "IsVirtualRegistry",
                "IsVirtualSystem", "HasLocalVirtualMachineDeviceCache"
            };
            var vmType = monModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Monitoring.VirtualMachineDetector");
            if (vmType != null)
            {
                Console.WriteLine($"\n[+] {vmType.FullName}");
                foreach (var m in vmType.Methods.Where(m => m.HasBody && Array.Exists(vmTargets, n => n == m.Name)))
                    allOk &= ReportStatus(m.Name, IsReturnBool(m, false), "returns false");
            }
            else
            {
                allOk = false;
            }

            var rsTargets = new[] { "IsRemoteSession", "IsWindowsRemoteDesktopSession", "IsWtsSession" };
            var rsType = monModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Monitoring.RemoteSessionDetector");
            if (rsType != null)
            {
                Console.WriteLine($"\n[+] {rsType.FullName}");
                foreach (var m in rsType.Methods.Where(m => m.HasBody && Array.Exists(rsTargets, n => n == m.Name)))
                    allOk &= ReportStatus(m.Name, IsReturnBool(m, false), "returns false");
            }

            var amTargets = new[] { "SystemEvent_WindowChanged", "Timer_Elapsed", "HandleInstanceStart", "HandleExplorerStart" };
            var amType = monModule.GetTypes().FirstOrDefault(t => t.Name == "ApplicationMonitor");
            if (amType != null)
            {
                Console.WriteLine($"\n[+] {amType.FullName}");
                foreach (var m in amType.Methods.Where(m => m.HasBody && Array.Exists(amTargets, n => n == m.Name)))
                    allOk &= ReportStatus(m.Name, IsReturnVoid(m), "void nop");
            }

            // 2. SafeExamBrowser.Configuration.dll
            var configPath = Path.Combine(sebPath, "SafeExamBrowser.Configuration.dll");
            if (File.Exists(configPath))
            {
                allOk &= CheckAssemblyHeader(configPath);
                var cfgModule = LoadModule(configPath);
                var imType = cfgModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Configuration.Integrity.IntegrityModule");
                if (imType != null)
                {
                    Console.WriteLine($"\n[+] {imType.FullName}");
                    foreach (var m in imType.Methods.Where(m => m.HasBody))
                    {
                        if (m.Name == "TryVerifyCodeSignature" || m.Name == "TryVerifySessionIntegrity")
                            allOk &= ReportStatus(m.Name, IsIntegrityOutBoolTrue(m), "out isValid=true, returns true");
                        else if (m.Name == "IsVirtualMachine")
                            allOk &= ReportStatus(m.Name, IsReturnFalseAtEnd(m), "returns false");
                        else if (m.Name == "TryCalculateBrowserExamKey" ||
                                 m.Name == "TryCalculateAppSignatureKey" ||
                                 m.Name == "TryReadSessionCache")
                        {
                            bool untouched = !IsReturnBool(m, true) && !IsReturnBool(m, false);
                            allOk &= ReportStatus(m.Name, untouched, "PRESERVED (original)");
                        }
                    }
                }
            }
            else
            {
                Console.WriteLine($"\n[!] Missing: {configPath}");
                allOk = false;
            }

            // 3. SafeExamBrowser.UserInterface.Shared.dll
            var uiSharedPath = Path.Combine(sebPath, "SafeExamBrowser.UserInterface.Shared.dll");
            if (File.Exists(uiSharedPath))
            {
                allOk &= CheckAssemblyHeader(uiSharedPath);
                var uiModule = LoadModule(uiSharedPath);
                var weType = uiModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.UserInterface.Shared.Utilities.WindowExtensions");
                if (weType != null)
                {
                    Console.WriteLine($"\n[+] {weType.FullName}");
                    var m = weType.Methods.FirstOrDefault(x => x.Name == "ExcludeFromCapture" && x.HasBody);
                    if (m != null)
                        allOk &= ReportStatus(m.Name, IsReturnBool(m, true), "returns true (capture allowed)");
                }
            }
            else
            {
                Console.WriteLine($"\n[!] Missing: {uiSharedPath}");
                allOk = false;
            }

            // 4. SafeExamBrowser.Client.exe
            var clientPath = Path.Combine(sebPath, "SafeExamBrowser.Client.exe");
            if (File.Exists(clientPath))
            {
                allOk &= CheckAssemblyHeader(clientPath);
                var clientModule = LoadModule(clientPath);
                var wgType = clientModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Client.Operations.WindowGuardOperation");
                if (wgType != null)
                {
                    Console.WriteLine($"\n[+] {wgType.FullName}");
                    var m = wgType.Methods.FirstOrDefault(x => x.Name == "Perform" && x.HasBody);
                    if (m != null)
                        allOk &= ReportStatus(m.Name, IsReturnInt(m, OperationResultSuccess), "OperationResult.Success");
                }
                var monResp = clientModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Client.Responsibilities.MonitoringResponsibility");
                if (monResp != null)
                {
                    Console.WriteLine($"\n[+] {monResp.FullName}");
                    var m = monResp.Methods.FirstOrDefault(x => x.Name == "Sentinel_SessionChanged" && x.HasBody);
                    if (m != null)
                        allOk &= ReportStatus(m.Name, IsReturnVoid(m), "void nop");
                }
                var intResp = clientModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Client.Responsibilities.IntegrityResponsibility");
                if (intResp != null)
                {
                    Console.WriteLine($"\n[+] {intResp.FullName}");
                    foreach (var name in new[] { "VerifyApplicationIntegrity", "VerifySessionIntegrity" })
                    {
                        var m = intResp.Methods.FirstOrDefault(x => x.Name == name && x.HasBody);
                        if (m != null)
                            allOk &= ReportStatus(m.Name, IsReturnVoid(m), "void nop");
                    }
                }
            }
            else
            {
                Console.WriteLine($"\n[!] Missing: {clientPath}");
                allOk = false;
            }

            // 5. SafeExamBrowser.exe
            var runtimePath = Path.Combine(sebPath, "SafeExamBrowser.exe");
            if (File.Exists(runtimePath))
            {
                allOk &= CheckAssemblyHeader(runtimePath);
                var rtModule = LoadModule(runtimePath);
                foreach (var opName in new[] { "VirtualMachineOperation", "RemoteSessionOperation", "ApplicationIntegrityOperation", "SessionIntegrityOperation" })
                {
                    var opType = rtModule.GetTypes().FirstOrDefault(t => t.Name == opName);
                    if (opType == null) continue;
                    Console.WriteLine($"\n[+] {opType.FullName}");
                    foreach (var m in opType.Methods.Where(m => m.HasBody && (m.Name == "Perform" || m.Name == "Repeat" || m.Name == "ValidatePolicy")))
                        allOk &= ReportStatus(m.Name, IsReturnInt(m, OperationResultSuccess), "OperationResult.Success");
                }

                var svcType = rtModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Runtime.Operations.Session.ServiceOperation");
                if (svcType != null)
                {
                    Console.WriteLine($"\n[+] {svcType.FullName}");
                    foreach (var m in svcType.Methods.Where(m => m.HasBody && (m.Name == "Perform" || m.Name == "Repeat")))
                        allOk &= ReportStatus(m.Name, IsReturnInt(m, OperationResultSuccess), "OperationResult.Success");
                }

                var kioskType = rtModule.GetTypes().FirstOrDefault(t => t.FullName == "SafeExamBrowser.Runtime.Operations.Session.KioskModeOperation");
                if (kioskType != null)
                {
                    Console.WriteLine($"\n[+] {kioskType.FullName}");
                    var m = kioskType.Methods.FirstOrDefault(x => x.Name == "CreateCustomDesktop" && x.HasBody);
                    if (m != null)
                        allOk &= ReportStatus(m.Name, IsKioskCreateCustomDesktopPatched(m), "skips custom desktop under RDP");
                }
            }
            else
            {
                Console.WriteLine($"\n[!] Missing: {runtimePath}");
                allOk = false;
            }

            // 6. SafeExamBrowser.Lockdown.dll (optional if Service folder is alongside)
            var lockdownPath = ResolveLockdownPath(sebPath);
            if (lockdownPath != null)
            {
                allOk &= CheckAssemblyHeader(lockdownPath);
                var ldModule = LoadModule(lockdownPath);
                var rcType = ldModule.GetTypes().FirstOrDefault(
                    t => t.FullName == "SafeExamBrowser.Lockdown.FeatureConfigurations.RegistryConfigurations.MachineHive.RemoteConnectionConfiguration");
                if (rcType != null)
                {
                    Console.WriteLine($"\n[+] {rcType.FullName}");
                    var m = rcType.Methods.FirstOrDefault(x => x.Name == "get_Items" && x.HasBody);
                    if (m != null)
                        allOk &= ReportStatus(m.Name, IsReturnEmptyArray(m), "returns empty array");
                }
            }

            Console.WriteLine();
            if (allOk)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("[+] Overall check: ALL TARGET PATCHES VERIFIED");
                Console.ResetColor();
                return 0;
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[!] Overall check: ONE OR MORE TARGETS ARE UNPATCHED OR MISSING");
                Console.ResetColor();
                return 1;
            }
        }

        static bool CheckAssemblyHeader(string path)
        {
            var mod = LoadModule(path);
            Console.WriteLine($"\n[*] Assembly: {Path.GetFileName(path)} ({mod.Assembly?.FullName ?? mod.Name}) | Backup: {File.Exists(path + ".bak")}");
            return true;
        }

        static bool ReportStatus(string methodName, bool ok, string expectedDesc)
        {
            if (ok)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine($"  [+] {methodName}: PATCHED ({expectedDesc})");
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"  [-] {methodName}: NOT MATCHED (expected {expectedDesc})");
            }
            Console.ResetColor();
            return ok;
        }

        static bool IsReturnBool(MethodDef m, bool val)
        {
            var expectedOp = val ? OpCodes.Ldc_I4_1 : OpCodes.Ldc_I4_0;
            return m.Body.Instructions.Count == 2 &&
                   m.Body.Instructions[0].OpCode == expectedOp &&
                   m.Body.Instructions[1].OpCode == OpCodes.Ret;
        }

        static bool IsReturnFalseAtEnd(MethodDef m)
        {
            var instrs = m.Body.Instructions;
            return instrs.Count >= 2 &&
                   instrs[instrs.Count - 2].OpCode == OpCodes.Ldc_I4_0 &&
                   instrs[instrs.Count - 1].OpCode == OpCodes.Ret;
        }

        static bool IsIntegrityOutBoolTrue(MethodDef m)
        {
            var instrs = m.Body.Instructions;
            return instrs.Count == 5 &&
                   (instrs[0].OpCode == OpCodes.Ldarg || instrs[0].OpCode == OpCodes.Ldarg_S ||
                    instrs[0].OpCode == OpCodes.Ldarg_1 || instrs[0].OpCode == OpCodes.Ldarg_2 || instrs[0].OpCode == OpCodes.Ldarg_3) &&
                   instrs[1].OpCode == OpCodes.Ldc_I4_1 &&
                   instrs[2].OpCode == OpCodes.Stind_I1 &&
                   instrs[3].OpCode == OpCodes.Ldc_I4_1 &&
                   instrs[4].OpCode == OpCodes.Ret;
        }

        static bool IsReturnVoid(MethodDef m)
        {
            return m.Body.Instructions.Count == 1 &&
                   m.Body.Instructions[0].OpCode == OpCodes.Ret;
        }

        static bool IsReturnInt(MethodDef m, int value)
        {
            if (m.Body.Instructions.Count != 2 || m.Body.Instructions[1].OpCode != OpCodes.Ret)
                return false;
            var i0 = m.Body.Instructions[0];
            if (i0.OpCode == OpCodes.Ldc_I4 && i0.Operand is int v) return v == value;
            if (i0.OpCode == OpCodes.Ldc_I4_S && i0.Operand is sbyte sb) return sb == value;
            if (value == 3 && i0.OpCode == OpCodes.Ldc_I4_3) return true;
            return false;
        }

        static bool IsReturnEmptyArray(MethodDef m)
        {
            var instrs = m.Body.Instructions;
            return instrs.Count == 3 &&
                   instrs[0].OpCode == OpCodes.Ldc_I4_0 &&
                   instrs[1].OpCode == OpCodes.Newarr &&
                   instrs[2].OpCode == OpCodes.Ret;
        }

        static void PrintBanner(string version = "3.10.x")
        {
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($@"
  ____  ____  _   _    _    ____
 / ___|| __ )| \ | |  / \  |  _ \
 \___ \|  _ \|  \| | / _ \ | |_) |
  ___) | |_) | |\  |/ ___ \|  __/
 |____/|____/|_| \_/_/   \_\_|
  Safe Exam Browser IL Patcher (v{version})
");
            Console.ResetColor();
        }

        static void PrintUsage()
        {
            Console.WriteLine("Usage:");
            Console.WriteLine("  seb-patcher patch [SEB_PATH | --path <dir>]   - Patch SEB assemblies (VM, Integrity, RDP)");
            Console.WriteLine("  seb-patcher restore [SEB_PATH | --path <dir>] - Restore original assemblies from .bak");
            Console.WriteLine("  seb-patcher check [SEB_PATH | --path <dir>]   - Verify all target patches and backups");
            Console.WriteLine();
            Console.WriteLine($"SEB_PATH defaults to: {DefaultSebPath}");
            Console.WriteLine();
            Console.WriteLine("IMPORTANT: Run as Administrator when patching Program Files!");
        }
    }
}
