using System;
using System.IO;
using System.Linq;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;

MetadataReference[] references = ((string)AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES")!)
    .Split(Path.PathSeparator).Distinct().Select(path => MetadataReference.CreateFromFile(path)).ToArray();
CompilerContract.Verify(references);
Console.WriteLine("Compiler/runtime positive and negative controls passed: " + typeof(CSharpCompilation).Assembly.FullName);
