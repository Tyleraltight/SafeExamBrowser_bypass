using dnlib.DotNet;
using dnlib.DotNet.Emit;
using System;
using System.IO;

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
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[!] VirtualMachineDetector type not found!");
                Console.ResetColor();
                return 1;
            }

            Console.WriteLine($"[+] Found type: {vmDetectorType.FullName}");

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

        static void PrintBanner()
        {
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine(@"
  ____  ____  _   _    _    ____
 / ___|| __ )| \ | |  / \  |  _ \
 \___ \|  _ \|  \| | / _ \ | |_) |
  ___) | |_) | |\  |/ ___ \|  __/
 |____/|____/|_| \_/_/   \_\_|
  Safe Exam Browser v3.10.1 IL Patcher
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
