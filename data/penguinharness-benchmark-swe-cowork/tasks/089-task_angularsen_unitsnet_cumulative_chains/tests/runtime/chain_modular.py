from __future__ import annotations

from probe_helpers import modular_runtime_reflection_probe, run_modular_probe, try_modular_probe


def _compile_with_historical_fallback(current_source: str, historical_source: str) -> None:
    current_compile, current_run = try_modular_probe(current_source)
    if current_compile.returncode == 0:
        assert current_run is not None
        assert current_run.returncode == 0, current_run.stdout + current_run.stderr
        return

    historical_compile, historical_run = try_modular_probe(historical_source)
    assert historical_compile.returncode == 0, (
        "current API compile:\n"
        + current_compile.stdout
        + current_compile.stderr
        + "\nhistorical API compile:\n"
        + historical_compile.stdout
        + historical_compile.stderr
    )
    assert historical_run is not None
    assert historical_run.returncode == 0, historical_run.stdout + historical_run.stderr


def check_1705_consumer_owned_generation() -> None:
    body = r'''
using System;
using UnitsNet;
using UnitsNet.Modular;
using UnitsNet.Units;
using Catalog = UnitsNet.Modular.BuiltIns;

[UnitsNetModule]
internal interface ProbeModule : IInclude<Catalog.__SPEC__>;

static class Probe
{
    static void Main()
    {
        Length length = Length.FromMeters(2.5);
        Length converted = length.ToUnit(LengthUnit.Centimeter);
        if (Math.Abs(converted.Value - 250) > 1e-12 || converted.Unit != LengthUnit.Centimeter)
            throw new Exception("consumer-owned generated conversion is incorrect");
        if (!Length.TryParse("3.5 m", out Length parsed) || Math.Abs(parsed.Meters - 3.5) > 1e-12)
            throw new Exception("consumer-owned generated parsing is unavailable");
    }
}
'''
    _compile_with_historical_fallback(
        body.replace("__SPEC__", "LengthSpec"),
        body.replace("__SPEC__", "Length"),
    )
    from project_consumer import check_project_consumer
    check_project_consumer()


def check_1708_standard_authoring_names() -> None:
    run_modular_probe(
        r'''
using System;
using UnitsNet;
using UnitsNet.Modular;
using Catalog = UnitsNet.Modular.BuiltIns;
using Profiles = UnitsNet.Modular.Profiles;

[UnitsNetModule]
internal interface ProbeModule : IInclude<Catalog.LengthSpec>, IIncludeProfile<Profiles.AllSiProfile>;

static class Probe
{
    static void Main()
    {
        if (typeof(Catalog.LengthSpec).Name != "LengthSpec")
            throw new Exception("built-in spec did not use the standardized suffix");
        if (typeof(Profiles.AllSiProfile).Name != "AllSiProfile")
            throw new Exception("profile did not use the standardized suffix");
        if (Math.Abs(Length.FromMeters(1).Centimeters - 100) > 1e-12)
            throw new Exception("standardized authoring types did not drive generation");
    }
}
'''
    )


def check_1709_semantic_id_selection() -> None:
    body = r'''
using System;
using UnitsNet;
using UnitsNet.Modular;

[__ATTRIBUTE__("UnitsNet.Length")]
internal interface CompletelyUnrelatedMarkerName;

[UnitsNetModule]
internal interface ProbeModule : IInclude<CompletelyUnrelatedMarkerName>;

static class Probe
{
    static void Main()
    {
        Length length = Length.FromMeters(4);
        if (Math.Abs(length.Centimeters - 400) > 1e-12)
            throw new Exception("semantic ID did not select the built-in Length definition");
    }
}
'''
    _compile_with_historical_fallback(
        body.replace("__ATTRIBUTE__", "QuantitySpec"),
        body.replace("__ATTRIBUTE__", "QuantityDefinition"),
    )


def check_1710_quantity_spec_attribute_contract() -> None:
    run_modular_probe(
        r'''
using System;
using UnitsNet;
using UnitsNet.Modular;

[QuantitySpec("UnitsNet.Length")]
internal interface DistanceContract;

[UnitsNetModule]
internal interface ProbeModule : IInclude<DistanceContract>;

static class Probe
{
    static void Main()
    {
        var attribute = (QuantitySpecAttribute)Attribute.GetCustomAttribute(
            typeof(DistanceContract), typeof(QuantitySpecAttribute))!;
        if (attribute.SemanticId != "UnitsNet.Length")
            throw new Exception("QuantitySpecAttribute did not expose its semantic ID");
        if (Math.Abs(Length.FromMeters(1).Millimeters - 1000) > 1e-12)
            throw new Exception("QuantitySpecAttribute did not participate in generation");
    }
}
'''
    )


def check_1715_canonical_metadata_registry() -> None:
    run_modular_probe(
        r'''
using System;
using UnitsNet;
using UnitsNet.Modular;
using Catalog = UnitsNet.Modular.BuiltIns;

[UnitsNetModule]
internal interface ProbeModule : IInclude<Catalog.LengthSpec>;

static class Probe
{
    static void Main()
    {
        IQuantityDescriptor registered = Quantity.Registry.Get(typeof(Length));
        if (!object.ReferenceEquals(Length.Info, registered))
            throw new Exception("generated static Info and the module registry are not canonical");
        if (registered.Id.Value != "UnitsNet.Length" || registered.Name != "Length")
            throw new Exception("consolidated metadata lost its stable identity");
        IQuantity<double> created = registered.Create(2.5, "Meter");
        if (Math.Abs(registered.GetValue(created) - 2.5) > 1e-12)
            throw new Exception("registry metadata cannot execute the generated quantity contract");
    }
}
'''
    )


def check_1717_diagnostic_help_links() -> None:
    modular_runtime_reflection_probe(
        r'''
using System;
using System.IO;
using System.Linq;
using System.Reflection;

static class Probe
{
    static void Main()
    {
        Assembly assembly = Assembly.LoadFrom(Path.Combine(AppContext.BaseDirectory, Environment.GetCommandLineArgs()[1]));
        object[] descriptors = assembly.GetTypes()
            .SelectMany(type => type.GetFields(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
            .Where(field => field.FieldType.FullName == "Microsoft.CodeAnalysis.DiagnosticDescriptor")
            .Select(field => field.GetValue(null)!)
            .Concat(assembly.GetTypes()
                .SelectMany(type => type.GetProperties(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
                .Where(property => property.PropertyType.FullName == "Microsoft.CodeAnalysis.DiagnosticDescriptor" &&
                                   property.GetIndexParameters().Length == 0)
                .Select(property => property.GetValue(null)!))
            .Distinct()
            .ToArray();
        if (descriptors.Length != 13)
            throw new Exception($"expected 13 UNM diagnostic descriptors, found {descriptors.Length}");

        foreach (object descriptor in descriptors)
        {
            Type type = descriptor.GetType();
            string id = (string)type.GetProperty("Id")!.GetValue(descriptor)!;
            string? help = (string?)type.GetProperty("HelpLinkUri")!.GetValue(descriptor);
            if (!id.StartsWith("UNM", StringComparison.Ordinal) ||
                string.IsNullOrWhiteSpace(help) ||
                !help.StartsWith("https://github.com/angularsen/UnitsNet/tree/master/UnitsNet.Modular#", StringComparison.Ordinal))
                throw new Exception($"{id} has no focused UnitsNet.Modular documentation link");
        }
    }
}
'''
    )


def check_1716_numeric_format_annotations() -> None:
    run_modular_probe(
        r'''
using System;
using System.Diagnostics.CodeAnalysis;
using System.Linq;
using System.Reflection;
using UnitsNet;
using UnitsNet.Modular;
using Catalog = UnitsNet.Modular.BuiltIns;

[UnitsNetModule]
internal interface ProbeModule : IInclude<Catalog.LengthSpec>;

static class Probe
{
    static void RequireNumericFormat(ParameterInfo parameter, string owner)
    {
        CustomAttributeData attribute = parameter.CustomAttributes.Single(
            item => item.AttributeType.FullName == typeof(StringSyntaxAttribute).FullName);
        if ((string?)attribute.ConstructorArguments[0].Value != StringSyntaxAttribute.NumericFormat)
            throw new Exception(owner + " does not describe a numeric format string");
    }

    static void Main()
    {
        MethodInfo descriptorFormat = typeof(IQuantityDescriptor).GetMethod("Format")!;
        RequireNumericFormat(descriptorFormat.GetParameters().Single(parameter => parameter.Name == "format"),
                             "IQuantityDescriptor.Format");

        MethodInfo generatedFormat = typeof(Length).GetMethods()
            .Single(method => method.Name == "ToString" &&
                              method.GetParameters().Length == 2 &&
                              method.GetParameters()[0].ParameterType == typeof(string));
        RequireNumericFormat(generatedFormat.GetParameters()[0], "Length.ToString");
    }
}
'''
    )
