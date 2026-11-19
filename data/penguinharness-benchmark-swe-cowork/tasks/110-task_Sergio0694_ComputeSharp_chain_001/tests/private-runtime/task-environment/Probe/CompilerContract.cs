using System;
using System.IO;
using System.Linq;
using System.Reflection;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;

internal static class CompilerContract
{
    public static void Verify(MetadataReference[] references)
    {
        const string source = """
            using System.Runtime.CompilerServices;
            public static class CompilerContractFixture
            {
                public static int Read()
                {
                    int value = 17;
                    return Unsafe.AsRef(in value);
                }
            }
            """;
        CSharpParseOptions parseOptions = new(LanguageVersion.Preview);
        CSharpCompilation Create(string text) => CSharpCompilation.Create(
            "CompilerContractFixture", new[] { CSharpSyntaxTree.ParseText(text, parseOptions) },
            references, new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
        using MemoryStream output = new();
        var emitted = Create(source).Emit(output);
        if (!emitted.Success)
        {
            throw new TypeLoadException("probe compiler/runtime mismatch: " +
                typeof(CSharpCompilation).Assembly.FullName + "; " +
                string.Join("; ", emitted.Diagnostics.Where(item => item.Severity == DiagnosticSeverity.Error)));
        }
        object? value = Assembly.Load(output.ToArray()).GetType("CompilerContractFixture")!
            .GetMethod("Read")!.Invoke(null, null);
        if (value is not int result || result != 17)
        {
            throw new TypeLoadException("probe compiler/runtime control returned an incorrect value");
        }
        if (!Create(source.Replace("AsRef(in value)", "AsRef(out value)")).GetDiagnostics()
            .Any(item => item.Severity == DiagnosticSeverity.Error))
        {
            throw new TypeLoadException("probe compiler accepted an invalid argument modifier");
        }
    }
}
