using dnlib.DotNet;
using dnlib.DotNet.Emit;
using System;
using System.IO;
using System.Linq;

namespace SebPatcher
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.OutputEncoding = System.Text.Encoding.UTF8;
            PrintBanner();

            if (args.Length < 1)
            {
                PrintUsage();
                return 1;
            }

            var command = args[0].ToLower();

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

        static int Patch(string[] args)
        {
            var sebPath = args.Length > 1 ? args[1] : @"C:\Program Files\SafeExamBrowser\Application";
            var dllPath = Path.Combine(sebPath, "SafeExamBrowser.Monitoring.dll");

            if (!File.Exists(dllPath))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[!] DLL not found: {dllPath}");
                Console.ResetColor();
                return 1;
            }

            // Backup
            var backupPath = dllPath + ".bak";
            if (!File.Exists(backupPath))
            {
                File.Copy(dllPath, backupPath, false);
                Console.WriteLine($"[+] Backup created: {backupPath}");
            }
            else
            {
                Console.WriteLine($"[*] Backup already exists: {backupPath}");
            }

            // Load assembly into memory to avoid file locking
            var moduleCtx = new ModuleContext();
            var dllBytes = File.ReadAllBytes(dllPath);
            var module = ModuleDefMD.Load(dllBytes, moduleCtx);
            module.Context = moduleCtx;

            Console.WriteLine($"[+] Loaded: {module.Assembly.FullName}");

            // Find VirtualMachineDetector
            TypeDef vmDetectorType = null;
            foreach (var type in module.GetTypes())
            {
                if (type.FullName == "SafeExamBrowser.Monitoring.VirtualMachineDetector")
                {
                    vmDetectorType = type;
                    break;
                }
            }

            if (vmDetectorType == null)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[!] VirtualMachineDetector type not found!");
                Console.ResetColor();
            }
            else
            {
                Console.WriteLine($"[+] Found type: {vmDetectorType.FullName}");
            }

            // Find RemoteSessionDetector
            TypeDef remoteSessionType = null;
            foreach (var type in module.GetTypes())
            {
                if (type.FullName == "SafeExamBrowser.Monitoring.RemoteSessionDetector")
                {
                    remoteSessionType = type;
                    break;
                }
            }

            if (remoteSessionType != null)
                Console.WriteLine($"[+] Found type: {remoteSessionType.FullName}");

            // Find IntegrityModule
            TypeDef integrityModuleType = null;
            foreach (var type in module.GetTypes())
            {
                if (type.FullName == "SafeExamBrowser.Configuration.Integrity.IntegrityModule" || type.Name == "IntegrityModule")
                {
                    integrityModuleType = type;
                    break;
                }
            }

            if (integrityModuleType != null)
                Console.WriteLine($"[+] Found type: {integrityModuleType.FullName}");

            // Patch all VM detection methods to return false
            var patchedCount = 0;
            var methodsToPatch = new[]
            {
                "IsVirtualMachine",
                "HasNoSystemHardware",
                "HasVirtualDevice",
                "HasVirtualMacAddress",
                "IsVirtualCpu",
                "IsVirtualRegistry",
                "IsVirtualSystem"
            };

            // Patch all RemoteSession methods to return false as well
            var remoteSessionMethods = new[]
            {
                "IsRemoteSession",
                "IsWindowsRemoteDesktopSession",
                "IsWtsSession"
            };

            if (vmDetectorType != null)
            {
                foreach (var method in vmDetectorType.Methods)
                {
                    if (Array.Exists(methodsToPatch, m => m == method.Name) && method.HasBody)
                    {
                        PatchReturnFalse(method);
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine($"  [+] Patched: {method.Name}");
                        Console.ResetColor();
                        patchedCount++;
                    }
                }
            }

            if (remoteSessionType != null)
            {
                foreach (var method in remoteSessionType.Methods)
                {
                    if (Array.Exists(remoteSessionMethods, m => m == method.Name) && method.HasBody)
                    {
                        PatchReturnFalse(method);
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine($"  [+] Patched (Remote): {method.Name}");
                        Console.ResetColor();
                        patchedCount++;
                    }
                }
            }

            if (integrityModuleType != null)
            {
                foreach (var method in integrityModuleType.Methods)
                {
                    // Patch all bool-returning methods in IntegrityModule, regardless of name.
                    // This ensures compatibility with future SEB versions that may add new
                    // integrity check methods without predictable naming patterns.
                    if (method.HasBody && method.ReturnType.FullName == "System.Boolean")
                    {
                        PatchReturnTrue(method);
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine($"  [+] Patched (Integrity): {method.Name} -> returns true");
                        Console.ResetColor();
                        patchedCount++;
                    }
                }
            }

            if (patchedCount == 0)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[!] No methods were patched!");
                Console.ResetColor();
                return 1;
            }

            // Save
            module.Write(dllPath);

            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine($"\n[+] Patched {patchedCount} methods successfully!");
            Console.WriteLine($"[+] Saved: {dllPath}");
            Console.ResetColor();

            // Verify
            Console.WriteLine("\n[*] Verifying patch...");
            var verifyBytes = File.ReadAllBytes(dllPath);
            var verifyModule = ModuleDefMD.Load(verifyBytes);
            foreach (var type in verifyModule.GetTypes())
            {
                if (type.FullName == "SafeExamBrowser.Monitoring.VirtualMachineDetector")
                {
                    foreach (var method in type.Methods)
                    {
                        if (Array.Exists(methodsToPatch, m => m == method.Name) && method.HasBody)
                        {
                            var isPatched = method.Body.Instructions.Count == 2 &&
                                           method.Body.Instructions[0].OpCode == OpCodes.Ldc_I4_0 &&
                                           method.Body.Instructions[1].OpCode == OpCodes.Ret;

                            if (isPatched)
                            {
                                Console.ForegroundColor = ConsoleColor.Green;
                                Console.WriteLine($"  [OK] {method.Name} -> returns false");
                            }
                            else
                            {
                                Console.ForegroundColor = ConsoleColor.Red;
                                Console.WriteLine($"  [FAIL] {method.Name} -> verification failed!");
                            }
                            Console.ResetColor();
                        }
                    }
                }
            }

            // ── Patch IntegrityModule in Configuration.dll ───────────────
            var configDllPath = Path.Combine(sebPath, "SafeExamBrowser.Configuration.dll");
            if (File.Exists(configDllPath))
            {
                Console.WriteLine("\n[*] Patching IntegrityModule in Configuration.dll...");

                var configBackup = configDllPath + ".bak";
                if (!File.Exists(configBackup))
                {
                    File.Copy(configDllPath, configBackup, false);
                    Console.WriteLine($"[+] Backup created: {configBackup}");
                }
                else
                {
                    Console.WriteLine($"[*] Backup already exists: {configBackup}");
                }

                var configBytes = File.ReadAllBytes(configDllPath);
                var configCtx = new ModuleContext();
                var configModule = ModuleDefMD.Load(configBytes, configCtx);
                configModule.Context = configCtx;

                var integrityPatchCount = 0;

                foreach (var type in configModule.GetTypes())
                {
                    // Patch IntegrityModule and all its nested types — VerifyCodeIntegrity and any bool integrity methods.
                    // Matching is intentionally broad to cover new methods added in future SEB versions.
                    if (type.Name == "IntegrityModule" || type.FullName.Contains("Integrity"))
                    {
                        Console.WriteLine($"[+] Found type: {type.FullName}");
                        foreach (var method in type.Methods)
                        {
                            if (!method.HasBody) continue;

                            // Patch ALL bool-returning methods (not just Verify/IsValid/Check)
                            // to ensure coverage against renamed or newly-added integrity checks.
                            if (method.ReturnType.FullName == "System.Boolean")
                            {
                                PatchReturnTrue(method);

                                Console.ForegroundColor = ConsoleColor.Green;
                                Console.WriteLine($"  [+] Patched (Integrity): {method.Name} -> returns true");
                                Console.ResetColor();
                                integrityPatchCount++;
                            }
                        }
                    }
                }

                if (integrityPatchCount > 0)
                {
                    configModule.Write(configDllPath);
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine($"\n[+] Patched {integrityPatchCount} integrity method(s) in Configuration.dll!");
                    Console.ResetColor();
                }
                else
                {
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine("[!] No integrity methods found in Configuration.dll");
                    Console.ResetColor();
                }
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"\n[!] Configuration.dll not found at: {configDllPath}");
                Console.WriteLine("    IntegrityModule was NOT patched — red lock screen may appear.");
                Console.ResetColor();
            }

            // ── Patch Client.exe — IntegrityResponsibility + MonitoringResponsibility ──
            var clientPath = Path.Combine(sebPath, "SafeExamBrowser.Client.exe");
            if (File.Exists(clientPath))
            {
                Console.WriteLine("\n[*] Patching SafeExamBrowser.Client.exe...");

                var clientBackup = clientPath + ".bak";
                if (!File.Exists(clientBackup))
                {
                    File.Copy(clientPath, clientBackup, false);
                    Console.WriteLine($"[+] Backup created: {clientBackup}");
                }

                var clientBytes = File.ReadAllBytes(clientPath);
                var clientCtx = new ModuleContext();
                var clientModule = ModuleDefMD.Load(clientBytes, clientCtx);
                clientModule.Context = clientCtx;
                var clientPatchCount = 0;

                foreach (var type in clientModule.GetTypes())
                {
                    // 1. IntegrityResponsibility — scheduled integrity timer + verify methods
                    if (type.Name == "IntegrityResponsibility" || type.FullName.Contains("IntegrityResponsibility"))
                    {
                        Console.WriteLine($"[+] Found type: {type.FullName}");
                        foreach (var method in type.Methods)
                        {
                            if (!method.HasBody || method.IsConstructor) continue;

                            bool shouldPatch = method.Name.Contains("Integrity") ||
                                               method.Name.Contains("Schedule") ||
                                               method.Name.Contains("Verify") ||
                                               method.Name.StartsWith("<"); // lambda callbacks

                            if (shouldPatch && method.ReturnType.FullName == "System.Void")
                            {
                                PatchReturnVoid(method);
                                Console.ForegroundColor = ConsoleColor.Green;
                                Console.WriteLine($"  [+] Patched (Client Integrity): {method.Name} -> void nop");
                                Console.ResetColor();
                                clientPatchCount++;
                            }
                        }
                    }

                    // 2. MonitoringResponsibility — Sentinel event handlers + display change
                    if (type.Name == "MonitoringResponsibility" || type.FullName.Contains("MonitoringResponsibility"))
                    {
                        Console.WriteLine($"[+] Found type: {type.FullName}");
                        foreach (var method in type.Methods)
                        {
                            if (!method.HasBody || method.IsConstructor) continue;

                            bool isSentinel = method.Name.Contains("Sentinel_") ||
                                             method.Name.Contains("DisplayMonitor_") ||
                                             method.Name.StartsWith("<"); // lambda callbacks

                            if (isSentinel && method.ReturnType.FullName == "System.Void")
                            {
                                PatchReturnVoid(method);
                                Console.ForegroundColor = ConsoleColor.Green;
                                Console.WriteLine($"  [+] Patched (Client Monitoring): {method.Name} -> void nop");
                                Console.ResetColor();
                                clientPatchCount++;
                            }
                        }
                    }
                }

                if (clientPatchCount > 0)
                {
                    clientModule.Write(clientPath);
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine($"\n[+] Patched {clientPatchCount} method(s) in Client.exe!");
                    Console.ResetColor();
                }
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"\n[!] Client.exe not found at: {clientPath}");
                Console.ResetColor();
            }

            // ── Patch SafeExamBrowser.exe (Runtime) — Operations ──
            // OperationResult enum: Aborted=1, Failed=2, Success=3
            var runtimePath = Path.Combine(sebPath, "SafeExamBrowser.exe");
            if (File.Exists(runtimePath))
            {
                Console.WriteLine("\n[*] Patching SafeExamBrowser.exe (Runtime)...");

                var rtBackup = runtimePath + ".bak";
                if (!File.Exists(rtBackup))
                {
                    File.Copy(runtimePath, rtBackup, false);
                    Console.WriteLine($"[+] Backup created: {rtBackup}");
                }

                var rtBytes = File.ReadAllBytes(runtimePath);
                var rtCtx = new ModuleContext();
                var rtModule = ModuleDefMD.Load(rtBytes, rtCtx);
                rtModule.Context = rtCtx;
                var rtPatchCount = 0;

                // Target operation type names and their methods to patch
                var targetOps = new[] {
                    "ApplicationIntegrityOperation",
                    "SessionIntegrityOperation",
                    "VirtualMachineOperation"
                };

                foreach (var type in rtModule.GetTypes())
                {
                    bool isTargetOp = Array.Exists(targetOps, t => type.Name == t);
                    if (!isTargetOp) continue;

                    Console.WriteLine($"[+] Found type: {type.FullName}");
                    foreach (var method in type.Methods)
                    {
                        if (!method.HasBody || method.IsConstructor) continue;

                        // Patch Perform/Repeat/Revert/ValidatePolicy → return OperationResult.Success (3)
                        bool isOpMethod = method.Name == "Perform" ||
                                         method.Name == "Repeat" ||
                                         method.Name == "Revert" ||
                                         method.Name == "ValidatePolicy";

                        if (isOpMethod && method.ReturnType.FullName.Contains("OperationResult"))
                        {
                            PatchReturnInt(method, 3); // 3 = OperationResult.Success
                            Console.ForegroundColor = ConsoleColor.Green;
                            Console.WriteLine($"  [+] Patched (Runtime): {method.Name} -> OperationResult.Success");
                            Console.ResetColor();
                            rtPatchCount++;
                        }

                        // Patch bool-returning verification methods → return true
                        if (method.ReturnType.FullName == "System.Boolean" &&
                            (method.Name.Contains("Verify") || method.Name.Contains("Initialize") ||
                             method.Name.Contains("Validate")))
                        {
                            PatchReturnTrue(method);
                            Console.ForegroundColor = ConsoleColor.Green;
                            Console.WriteLine($"  [+] Patched (Runtime): {method.Name} -> return true");
                            Console.ResetColor();
                            rtPatchCount++;
                        }

                        // Patch void methods that contain integrity/verification logic
                        if (method.ReturnType.FullName == "System.Void" &&
                            (method.Name.Contains("Verify") || method.Name.Contains("Finalize") ||
                             method.Name.Contains("Log")) &&
                            !method.Name.StartsWith("add_") && !method.Name.StartsWith("remove_"))
                        {
                            PatchReturnVoid(method);
                            Console.ForegroundColor = ConsoleColor.Green;
                            Console.WriteLine($"  [+] Patched (Runtime): {method.Name} -> void nop");
                            Console.ResetColor();
                            rtPatchCount++;
                        }
                    }
                }

                if (rtPatchCount > 0)
                {
                    rtModule.Write(runtimePath);
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine($"\n[+] Patched {rtPatchCount} method(s) in SafeExamBrowser.exe!");
                    Console.ResetColor();
                }
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"\n[!] SafeExamBrowser.exe not found at: {runtimePath}");
                Console.ResetColor();
            }

            return 0;
        }

        static void PatchReturnFalse(MethodDef method)
        {
            method.Body.Instructions.Clear();
            method.Body.ExceptionHandlers.Clear();
            method.Body.Variables.Clear();
            method.Body.InitLocals = false;

            // Replace with: ldc.i4.0; ret  (i.e., return false)
            method.Body.Instructions.Add(OpCodes.Ldc_I4_0.ToInstruction());
            method.Body.Instructions.Add(OpCodes.Ret.ToInstruction());
        }

        static void PatchReturnTrue(MethodDef method)
        {
            method.Body.Instructions.Clear();
            method.Body.ExceptionHandlers.Clear();
            method.Body.Variables.Clear();
            method.Body.InitLocals = false;

            // Replace with: ldc.i4.1; ret  (i.e., return true)
            method.Body.Instructions.Add(OpCodes.Ldc_I4_1.ToInstruction());
            method.Body.Instructions.Add(OpCodes.Ret.ToInstruction());
        }

        static void PatchReturnVoid(MethodDef method)
        {
            method.Body.Instructions.Clear();
            method.Body.ExceptionHandlers.Clear();
            method.Body.Variables.Clear();
            method.Body.InitLocals = false;

            // Replace with just: ret  (void no-op)
            method.Body.Instructions.Add(OpCodes.Ret.ToInstruction());
        }

        static void PatchReturnInt(MethodDef method, int value)
        {
            method.Body.Instructions.Clear();
            method.Body.ExceptionHandlers.Clear();
            method.Body.Variables.Clear();
            method.Body.InitLocals = false;

            // Replace with: ldc.i4 <value>; ret
            method.Body.Instructions.Add(OpCodes.Ldc_I4.ToInstruction(value));
            method.Body.Instructions.Add(OpCodes.Ret.ToInstruction());
        }

        static int Restore(string[] args)
        {
            var sebPath = args.Length > 1 ? args[1] : @"C:\Program Files\SafeExamBrowser\Application";
            var dllPath = Path.Combine(sebPath, "SafeExamBrowser.Monitoring.dll");
            var backupPath = dllPath + ".bak";

            if (!File.Exists(backupPath))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[!] Backup not found: {backupPath}");
                Console.ResetColor();
                return 1;
            }

            File.Copy(backupPath, dllPath, true);
            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine($"[+] Restored original DLL from backup");
            Console.ResetColor();
            return 0;
        }

        static int Check(string[] args)
        {
            var sebPath = args.Length > 1 ? args[1] : @"C:\Program Files\SafeExamBrowser\Application";
            var dllPath = Path.Combine(sebPath, "SafeExamBrowser.Monitoring.dll");

            if (!File.Exists(dllPath))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[!] DLL not found: {dllPath}");
                Console.ResetColor();
                return 1;
            }

            var backupPath = dllPath + ".bak";
            var moduleBytes = File.ReadAllBytes(dllPath);
            var module = ModuleDefMD.Load(moduleBytes);

            Console.WriteLine($"[+] Assembly: {module.Assembly.FullName}");
            Console.WriteLine($"[*] Has backup: {File.Exists(backupPath)}");

            foreach (var type in module.GetTypes())
            {
                if (type.FullName == "SafeExamBrowser.Monitoring.VirtualMachineDetector")
                {
                    Console.WriteLine($"\n[+] Type: {type.FullName}");
                    foreach (var method in type.Methods)
                    {
                        if (!method.HasBody) continue;

                        var isPatched = method.Body.Instructions.Count == 2 &&
                                       method.Body.Instructions[0].OpCode == OpCodes.Ldc_I4_0 &&
                                       method.Body.Instructions[1].OpCode == OpCodes.Ret;

                        if (isPatched)
                        {
                            Console.ForegroundColor = ConsoleColor.Green;
                            Console.WriteLine($"  [+] {method.Name}: PATCHED (returns false)");
                        }
                        else
                        {
                            Console.ForegroundColor = ConsoleColor.Yellow;
                            Console.WriteLine($"  [-] {method.Name}: ORIGINAL ({method.Body.Instructions.Count} instructions)");
                        }
                        Console.ResetColor();
                    }
                }
            }

            return 0;
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
            Console.WriteLine("  seb-patcher patch [SEB_PATH]   - Patch DLL to disable VM detection");
            Console.WriteLine("  seb-patcher restore [SEB_PATH]  - Restore original DLL from backup");
            Console.WriteLine("  seb-patcher check [SEB_PATH]    - Check if DLL is patched");
            Console.WriteLine();
            Console.WriteLine("SEB_PATH defaults to: C:\\Program Files\\SafeExamBrowser\\Application");
            Console.WriteLine();
            Console.WriteLine("IMPORTANT: Run as Administrator!");
        }
    }
}
