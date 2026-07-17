using Mono.Cecil;
using Mono.Cecil.Cil;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

class Program
{
    static void Main(string[] args)
    {
        Console.WriteLine("========================================");
        Console.WriteLine("  SEB Display Patcher v6.0");
        Console.WriteLine("========================================\n");

        string dllPath = @"C:\Program Files\SafeExamBrowser\Application\SafeExamBrowser.Monitoring.dll";

        // Output to the EXE's own directory (shared folder) to avoid permission issues
        string exeDir = Path.GetDirectoryName(System.Diagnostics.Process.GetCurrentProcess().MainModule?.FileName ?? Directory.GetCurrentDirectory());
        string outputPath = Path.Combine(exeDir, "SafeExamBrowser.Monitoring.dll");

        Console.WriteLine("[*] Source: " + dllPath);
        Console.WriteLine("[*] Output: " + outputPath);

        if (!File.Exists(dllPath))
        {
            Console.WriteLine("[ERROR] SEB DLL not found! Is SEB installed?");
            Console.ReadKey();
            return;
        }

        // Kill SEB
        try
        {
            foreach (var name in new[] { "SafeExamBrowser", "SafeExamBrowser.Service" })
            {
                foreach (var p in System.Diagnostics.Process.GetProcessesByName(name))
                {
                    Console.WriteLine("[*] Killing " + name + " PID " + p.Id);
                    try { p.Kill(); } catch { }
                }
            }
            var psi = new System.Diagnostics.ProcessStartInfo("cmd", "/c net stop SafeExamBrowser.Service")
            { UseShellExecute = false, CreateNoWindow = true };
            var proc = System.Diagnostics.Process.Start(psi);
            proc?.WaitForExit(5000);
            System.Threading.Thread.Sleep(2000);
        }
        catch { }

        Console.WriteLine("[*] Opening DLL...");
        var resolver = new DefaultAssemblyResolver();
        string dotnetDir = @"C:\Windows\Microsoft.NET\Framework64\v4.0.30319";
        string sebDir = Path.GetDirectoryName(dllPath);
        if (Directory.Exists(dotnetDir)) resolver.AddSearchDirectory(dotnetDir);
        if (Directory.Exists(sebDir)) resolver.AddSearchDirectory(sebDir);

        var assembly = AssemblyDefinition.ReadAssembly(dllPath,
            new ReaderParameters { AssemblyResolver = resolver });

        // Find List<T>
        TypeReference listTypeRef = null;
        MethodReference listCtorRef = null;

        Console.WriteLine("[*] Resolving List<T>...");
        foreach (var asmRef in assembly.MainModule.AssemblyReferences)
        {
            try
            {
                var resolved = resolver.Resolve(asmRef);
                if (resolved == null) continue;
                var listType = resolved.MainModule.Types.FirstOrDefault(
                    t => t.FullName == "System.Collections.Generic.List`1");
                if (listType != null)
                {
                    Console.WriteLine("[+] Found List<T> in " + asmRef.Name);
                    listTypeRef = listType;
                    listCtorRef = listType.Methods.FirstOrDefault(
                        m => m.IsConstructor && m.Parameters.Count == 0);
                    break;
                }
            }
            catch { }
        }

        int patchCount = 0;
        foreach (var module in assembly.Modules)
        {
            PatchAllTypes(module.Types, ref patchCount, listTypeRef, listCtorRef, resolver);
        }

        if (patchCount > 0)
        {
            if (assembly.Name.HasPublicKey)
            {
                assembly.Name.HasPublicKey = false;
                assembly.MainModule.Attributes &= ~ModuleAttributes.StrongNameSigned;
            }

            assembly.Write(outputPath, new WriterParameters { WriteSymbols = false });
            Console.WriteLine("\n========================================");
            Console.WriteLine("  SUCCESS! " + patchCount + " methods patched");
            Console.WriteLine("  Patched DLL saved to:");
            Console.WriteLine("  " + outputPath);
            Console.WriteLine("========================================");
            Console.WriteLine("\nNOW RUN fix_display.cmd AS ADMIN!");
        }
        else
        {
            Console.WriteLine("\n[!] Nothing was patched.");
        }

        Console.WriteLine("\nPress any key to exit.");
        Console.ReadKey();
    }

    static void PatchAllTypes(IEnumerable<TypeDefinition> types, ref int patchCount,
        TypeReference listTypeRef, MethodReference listCtorRef, DefaultAssemblyResolver resolver)
    {
        foreach (var type in types)
        {
            foreach (var method in type.Methods.Where(m => m.HasBody).ToList())
            {
                // 1. Patch TryLoadDisplays - make it return a working display list
                if (method.Name == "TryLoadDisplays")
                {
                    Console.WriteLine("[*] Patching TryLoadDisplays...");
                    PatchTryLoadDisplays(method, ref patchCount, listTypeRef, listCtorRef);
                }

                // 2. Patch ValidateConfiguration to ALWAYS return IsAllowed=true
                if (method.Name == "ValidateConfiguration" && method.ReturnType.Name == "ValidationResult")
                {
                    Console.WriteLine("[*] Patching ValidateConfiguration...");
                    PatchValidateConfiguration(method, ref patchCount, resolver);
                }

                // 3. Patch any lambda containing display validation
                if (method.Name.Contains("ValidateConfiguration") && method.ReturnType.Name == "Boolean")
                {
                    Console.WriteLine("[*] Patching lambda: " + method.Name);
                    PatchReturnTrue(method, ref patchCount);
                }

                // 4. Patch any method with WMI display strings
                bool hasWmi = method.Body.Instructions.Any(i =>
                    i.OpCode == OpCodes.Ldstr && i.Operand is string s &&
                    (s.Contains("WmiMonitor") || s.Contains("Root\\WMI")));
                if (hasWmi && method.ReturnType.Name == "Boolean")
                {
                    Console.WriteLine("[*] Patching WMI method: " + method.Name);
                    PatchReturnTrue(method, ref patchCount);
                }
            }

            // Recurse into nested types
            if (type.NestedTypes.Count > 0)
            {
                var nested = new TypeDefinition[type.NestedTypes.Count];
                type.NestedTypes.CopyTo(nested, 0);
                PatchAllTypes(nested, ref patchCount, listTypeRef, listCtorRef, resolver);
            }
        }
    }

    static void PatchValidateConfiguration(MethodDefinition method, ref int patchCount,
        DefaultAssemblyResolver resolver)
    {
        var module = method.Module;
        var il = method.Body.GetILProcessor();
        method.Body.Instructions.Clear();
        method.Body.Variables.Clear();
        method.Body.ExceptionHandlers.Clear();

        // Find ValidationResult type
        var vrType = method.ReturnType;
        var vrCtor = vrType.Resolve().Methods.FirstOrDefault(m => m.IsConstructor && !m.HasParameters);
        var isAllowedProp = vrType.Resolve().Properties.FirstOrDefault(p => p.Name == "IsAllowed");
        var extProp = vrType.Resolve().Properties.FirstOrDefault(p => p.Name == "ExternalDisplays");
        var intProp = vrType.Resolve().Properties.FirstOrDefault(p => p.Name == "InternalDisplays");

        var importedVrCtor = vrCtor != null ? module.ImportReference(vrCtor) : null;
        var importedIsAllowed = isAllowedProp?.SetMethod != null ? module.ImportReference(isAllowedProp.SetMethod) : null;
        var importedExtSet = extProp?.SetMethod != null ? module.ImportReference(extProp.SetMethod) : null;
        var importedIntSet = intProp?.SetMethod != null ? module.ImportReference(intProp.SetMethod) : null;

        if (importedVrCtor != null && importedIsAllowed != null)
        {
            var resultVar = new VariableDefinition(module.ImportReference(vrType));
            method.Body.Variables.Add(resultVar);

            // new ValidationResult()
            il.Append(il.Create(OpCodes.Newobj, importedVrCtor));
            il.Append(il.Create(OpCodes.Stloc, resultVar));

            // result.IsAllowed = true
            il.Append(il.Create(OpCodes.Ldloc, resultVar));
            il.Append(il.Create(OpCodes.Ldc_I4_1));
            il.Append(il.Create(OpCodes.Callvirt, importedIsAllowed));

            // result.InternalDisplays = 1
            if (importedIntSet != null)
            {
                il.Append(il.Create(OpCodes.Ldloc, resultVar));
                il.Append(il.Create(OpCodes.Ldc_I4_1));
                il.Append(il.Create(OpCodes.Callvirt, importedIntSet));
            }

            // result.ExternalDisplays = 0
            if (importedExtSet != null)
            {
                il.Append(il.Create(OpCodes.Ldloc, resultVar));
                il.Append(il.Create(OpCodes.Ldc_I4_0));
                il.Append(il.Create(OpCodes.Callvirt, importedExtSet));
            }

            // return result
            il.Append(il.Create(OpCodes.Ldloc, resultVar));
            il.Append(il.Create(OpCodes.Ret));

            method.Body.InitLocals = true;
            method.Body.MaxStackSize = 2;
            Console.WriteLine("    [+] -> returns ValidationResult(IsAllowed=true, Internal=1)");
            patchCount++;
        }
        else
        {
            Console.WriteLine("    [!] Could not resolve ValidationResult, falling back to TryLoadDisplays approach");
        }
    }

    static void PatchTryLoadDisplays(MethodDefinition method, ref int patchCount,
        TypeReference listTypeRef, MethodReference listCtorRef)
    {
        var il = method.Body.GetILProcessor();
        var module = method.Module;
        method.Body.Instructions.Clear();
        method.Body.Variables.Clear();
        method.Body.ExceptionHandlers.Clear();

        var outParam = method.Parameters.FirstOrDefault(p => p.ParameterType.IsByReference);

        if (outParam != null && listTypeRef != null && listCtorRef != null)
        {
            var importedListType = module.ImportReference(listTypeRef);
            var importedCtor = module.ImportReference(listCtorRef);

            var byRef = (ByReferenceType)outParam.ParameterType;
            var iListType = byRef.ElementType;
            TypeReference elementType = null;

            if (iListType is GenericInstanceType git && git.GenericArguments.Count > 0)
                elementType = git.GenericArguments[0];

            if (elementType != null)
            {
                var importedElementType = module.ImportReference(elementType);

                var concreteListType = new GenericInstanceType(importedListType);
                concreteListType.GenericArguments.Add(importedElementType);
                var importedConcreteList = module.ImportReference(concreteListType);

                var ctorRef = new MethodReference(".ctor",
                    module.TypeSystem.Void, importedConcreteList);
                ctorRef.HasThis = true;

                var listVar = new VariableDefinition(importedConcreteList);
                method.Body.Variables.Add(listVar);

                // new List<Display>()
                il.Append(il.Create(OpCodes.Newobj, ctorRef));
                il.Append(il.Create(OpCodes.Stloc, listVar));

                // Create and configure Display object
                TypeDefinition elementDef = null;
                try { elementDef = elementType.Resolve(); } catch { }

                if (elementDef != null)
                {
                    var displayCtor = elementDef.Methods.FirstOrDefault(
                        m => m.IsConstructor && !m.HasParameters);

                    if (displayCtor != null)
                    {
                        var importedCtor2 = module.ImportReference(displayCtor);
                        var displayVar = new VariableDefinition(importedElementType);
                        method.Body.Variables.Add(displayVar);

                        il.Append(il.Create(OpCodes.Newobj, importedCtor2));
                        il.Append(il.Create(OpCodes.Stloc, displayVar));

                        // Set ALL properties that affect validation
                        foreach (var prop in elementDef.Properties)
                        {
                            if (prop.SetMethod == null) continue;

                            var importedSetter = module.ImportReference(prop.SetMethod);

                            switch (prop.Name)
                            {
                                case "IsActive":
                                    il.Append(il.Create(OpCodes.Ldloc, displayVar));
                                    il.Append(il.Create(OpCodes.Ldc_I4_1));
                                    il.Append(il.Create(OpCodes.Callvirt, importedSetter));
                                    break;

                                case "IsPrimary":
                                    il.Append(il.Create(OpCodes.Ldloc, displayVar));
                                    il.Append(il.Create(OpCodes.Ldc_I4_1));
                                    il.Append(il.Create(OpCodes.Callvirt, importedSetter));
                                    break;

                                case "Identifier":
                                    il.Append(il.Create(OpCodes.Ldloc, displayVar));
                                    il.Append(il.Create(OpCodes.Ldstr, "Generic PnP Monitor"));
                                    il.Append(il.Create(OpCodes.Callvirt, importedSetter));
                                    break;
                            }
                        }

                        // Set Technology property if it exists (for IsInternal check)
                        try
                        {
                            var techProp = elementDef.Properties.FirstOrDefault(p => p.Name == "Technology");
                            if (techProp?.SetMethod != null)
                            {
                                var techType = techProp.PropertyType.Resolve();
                                if (techType != null && techType.IsEnum)
                                {
                                    var internalField = techType.Fields.FirstOrDefault(f => f.Name == "Internal");
                                    if (internalField != null)
                                    {
                                        var importedTechSetter = module.ImportReference(techProp.SetMethod);
                                        il.Append(il.Create(OpCodes.Ldloc, displayVar));
                                        long rawVal = Convert.ToInt64(internalField.Constant);
                                        il.Append(il.Create(OpCodes.Ldc_I4, unchecked((int)rawVal)));
                                        il.Append(il.Create(OpCodes.Callvirt, importedTechSetter));
                                        Console.WriteLine("    [+] Set Technology = Internal (0x" + rawVal.ToString("X") + ")");
                                    }
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine("    [!] Could not set Technology: " + ex.Message);
                        }

                        // list.Add(display)
                        var addRef = new MethodReference("Add",
                            module.TypeSystem.Void, importedConcreteList);
                        addRef.Parameters.Add(new ParameterDefinition(importedElementType));

                        il.Append(il.Create(OpCodes.Ldloc, listVar));
                        il.Append(il.Create(OpCodes.Ldloc, displayVar));
                        il.Append(il.Create(OpCodes.Callvirt, addRef));
                    }
                }

                // out displays = list
                il.Append(il.Create(OpCodes.Ldarg_1));
                il.Append(il.Create(OpCodes.Ldloc, listVar));
                il.Append(il.Create(OpCodes.Stind_Ref));
            }
            else
            {
                il.Append(il.Create(OpCodes.Ldarg_1));
                il.Append(il.Create(OpCodes.Ldnull));
                il.Append(il.Create(OpCodes.Stind_Ref));
            }
        }
        else
        {
            il.Append(il.Create(OpCodes.Ldarg_1));
            il.Append(il.Create(OpCodes.Ldnull));
            il.Append(il.Create(OpCodes.Stind_Ref));
        }

        // return true
        il.Append(il.Create(OpCodes.Ldc_I4_1));
        il.Append(il.Create(OpCodes.Ret));

        method.Body.InitLocals = true;
        method.Body.MaxStackSize = 2;
        Console.WriteLine("    [+] TryLoadDisplays -> returns true with fake internal display");
        patchCount++;
    }

    static void PatchReturnTrue(MethodDefinition method, ref int patchCount)
    {
        var il = method.Body.GetILProcessor();
        method.Body.Instructions.Clear();
        method.Body.Variables.Clear();
        method.Body.ExceptionHandlers.Clear();

        il.Append(il.Create(OpCodes.Ldc_I4_1));
        il.Append(il.Create(OpCodes.Ret));

        method.Body.InitLocals = false;
        method.Body.MaxStackSize = 1;
        Console.WriteLine("    [+] -> return true");
        patchCount++;
    }
}
