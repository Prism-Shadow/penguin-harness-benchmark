// Licensed under MIT No Attribution, see LICENSE file at the root.
// Copyright 2013 Andreas Gullberg Larsen (andreas.larsen84@gmail.com). Maintained at https://github.com/angularsen/UnitsNet.

using System;
using System.Globalization;
using UnitsNet.Units;
using Xunit;

namespace UnitsNet.Tests
{
    public class QuantityIFormattableTests
    {
        private static readonly Length MyLength = Length.FromFeet(1.2345678);
        
        private static readonly CultureInfo AmericanCulture = CultureInfo.GetCultureInfo("en-US");
        private static readonly CultureInfo NorwegianCulture = CultureInfo.GetCultureInfo("nb-NO");
        private static readonly CultureInfo RussianCulture = CultureInfo.GetCultureInfo("ru-RU");

        [Fact]
        public void GFormatStringEqualsToString()
        {
            Assert.Equal(MyLength.ToString("G"), MyLength.ToString());
        }

        [Fact]
        public void EmptyOrNullFormatStringEqualsGFormat()
        {
            Assert.Equal(MyLength.ToString("G"), MyLength.ToString(string.Empty));
            Assert.Equal(MyLength.ToString("G"), MyLength.ToString(format: null));
        }

        [Theory]
        [InlineData("a")]
        [InlineData("a0")]
        [InlineData("a1")]
        [InlineData("a2")]
        public void RemovedAbbreviationFormatsGiveMigrationGuidance(string format)
        {
            var error = Assert.Throws<FormatException>(() => MyLength.ToString(format, CultureInfo.InvariantCulture));
            Assert.Contains("UnitAbbreviationsCache", error.Message);
        }

        [Theory]
        [InlineData("S")]
        [InlineData("s")]
        [InlineData("S2")]
        [InlineData("s2")]
        [InlineData("S4")]
        [InlineData("s4")]
        public void RemovedSignificantDigitFormatsGiveMigrationGuidance(string format)
        {
            var error = Assert.Throws<FormatException>(() => MyLength.ToString(format, CultureInfo.InvariantCulture));
            Assert.Contains("numeric format", error.Message);
        }

        [Fact]
        public void AFormatWithInvalidIndexThrowsFormatException()
        {
            Assert.Throws<FormatException>(() => MyLength.ToString("a100"));
        }

        [Fact]
        public void UnsupportedFormatStringThrowsException()
        {
            Assert.Throws<FormatException>(() => MyLength.ToString("z"));
        }

        // The default, parameterless ToString() method represents the result with all significant digits, without a group separator.
        [Theory]
#if NET
        [InlineData(double.MinValue, "-1.7976931348623157E+308 m")]
#else
        [InlineData(double.MinValue, "-1.79769313486232E+308 m")]
#endif
        [InlineData(-0.819999999999, "-0.819999999999 m")]
        [InlineData(-0.111234, "-0.111234 m")]
        [InlineData(-0.1, "-0.1 m")]
        [InlineData(-0.0000012345, "-1.2345E-06 m")]
        [InlineData(-0.000001, "-1E-06 m")]
        [InlineData(0, "0 m")]
        [InlineData(0.000001, "1E-06 m")]
        [InlineData(0.0000012345, "1.2345E-06 m")]
        [InlineData(0.1, "0.1 m")]
        [InlineData(0.111234, "0.111234 m")]
        [InlineData(0.819999999999, "0.819999999999 m")]
#if NET
        [InlineData(double.MaxValue, "1.7976931348623157E+308 m")]
#else
        [InlineData(double.MaxValue, "1.79769313486232E+308 m")]
#endif
        public void DefaultToStringFormatting(double value, string expected)
        {
            string actual = Length.FromMeters(value).ToString(AmericanCulture);
            Assert.Equal(expected, actual);
        }
        [Theory]
        [InlineData("de-DE")]
        [InlineData("da-DK")]
        [InlineData("es-AR")]
        [InlineData("es-ES")]
        [InlineData("it-IT")]
        [InlineData("en-CA")]
        [InlineData("en-US")]
        [InlineData("ar-EG")]
        [InlineData("en-GB")]
        [InlineData("es-MX")]
        public void RadixPointCultureFormatting(string cultureName)
        {
            CultureInfo culture = CultureInfo.GetCultureInfo(cultureName);
            string ds = culture.NumberFormat.NumberDecimalSeparator;
            Assert.Equal($"0{ds}12 m", Length.FromMeters(0.12).ToString(culture));
        }

        [Theory]
        [InlineData("de-DE")]
        [InlineData("da-DK")]
        [InlineData("es-AR")]
        [InlineData("es-ES")]
        [InlineData("it-IT")]
        [InlineData("en-CA")]
        [InlineData("en-US")]
        [InlineData("ar-EG")]
        [InlineData("en-GB")]
        [InlineData("es-MX")]
        public void ToString_FixedPointFormat_DecimalSeparator_ForCulture(string cultureName)
        {
            CultureInfo culture = CultureInfo.GetCultureInfo(cultureName);
            string ds = culture.NumberFormat.NumberDecimalSeparator;
            Assert.Equal($"0{ds}12 m", Length.FromMeters(0.12).ToString("F2", culture));
        }

        [Theory]
        [InlineData("en-CA")]
        [InlineData("en-GB")]
        [InlineData("en-US")]
        [InlineData("ar-EG")]
        [InlineData("es-MX")]
        [InlineData("nn-NO")]
        [InlineData("fr-FR")]
        [InlineData("de-DE")]
        [InlineData("da-DK")]
        [InlineData("es-AR")]
        [InlineData("es-ES")]
        [InlineData("it-IT")]
        public void ToString_WithCultureWithoutGroupingSeparator(string cultureName)
        {
            CultureInfo culture = CultureInfo.GetCultureInfo(cultureName);
            Assert.Equal("1111 m", Length.FromMeters(1111).ToString(culture));
        }

        [Theory]
        [InlineData("en-CA")]
        [InlineData("en-GB")]
        [InlineData("en-US")]
        [InlineData("ar-EG")]
        [InlineData("es-MX")]
        [InlineData("nn-NO")]
        [InlineData("fr-FR")]
        [InlineData("de-DE")]
        [InlineData("da-DK")]
        [InlineData("es-AR")]
        [InlineData("es-ES")]
        [InlineData("it-IT")]
        public void ToString_NumberFormat_UsesGroupingSeparator_ForCulture(string cultureName)
        {
            CultureInfo culture = CultureInfo.GetCultureInfo(cultureName);
            string gs = culture.NumberFormat.NumberGroupSeparator;

            Assert.Equal($"1{gs}111 m", Length.FromMeters(1111).ToString("N0", culture));
        }

        [Theory]
        [InlineData("en-CA")]
        [InlineData("en-GB")]
        [InlineData("en-US")]
        [InlineData("ar-EG")]
        [InlineData("es-MX")]
        [InlineData("nn-NO")]
        [InlineData("fr-FR")]
        [InlineData("de-DE")]
        [InlineData("da-DK")]
        [InlineData("es-AR")]
        [InlineData("es-ES")]
        [InlineData("it-IT")]
        public void FeetInches_UseGroupingSeparator_ForCulture(string cultureName)
        {
            CultureInfo culture = CultureInfo.GetCultureInfo(cultureName);
            string gs = culture.NumberFormat.NumberGroupSeparator;

            // Feet/Inch and Stone/Pound combinations are only used (customarily) in the US, UK and maybe Ireland - all English speaking countries.
            // FeetInches returns a whole number of feet, with the remainder expressed (rounded) in inches. Same for StonePounds.
            Assert.Equal($"3{gs}333 st 7 lb", Mass.FromStonePounds(3333, 7).StonePounds.ToString(culture));
        }

        [Theory]
        [InlineData("en-CA")]
        [InlineData("en-GB")]
        [InlineData("en-US")]
        [InlineData("ar-EG")]
        [InlineData("es-MX")]
        [InlineData("nn-NO")]
        [InlineData("fr-FR")]
        [InlineData("de-DE")]
        [InlineData("da-DK")]
        [InlineData("es-AR")]
        [InlineData("es-ES")]
        [InlineData("it-IT")]
        public void StonePounds_UseGroupingSeparator_ForCulture(string cultureName)
        {
            CultureInfo culture = CultureInfo.GetCultureInfo(cultureName);
            string gs = culture.NumberFormat.NumberGroupSeparator;

            // Feet/Inch and Stone/Pound combinations are only used (customarily) in the US, UK and maybe Ireland - all English speaking countries.
            // FeetInches returns a whole number of feet, with the remainder expressed (rounded) in inches. Same for StonePounds.
            Assert.Equal($"3{gs}333 st 7 lb", Mass.FromStonePounds(3333, 7).StonePounds.ToString(culture));
        }

        // Standard numeric formats control rounding and precision.
        [Theory]
        [InlineData(-0.819999999999, "G", "-0.819999999999 m")]
        [InlineData(-0.819999999999, "F2", "-0.82 m")]
        [InlineData(-0.819999999999, "G4", "-0.82 m")]
        [InlineData(-0.8, "G4", "-0.8 m")]
        [InlineData(0.819999999999, "G", "0.819999999999 m")]
        [InlineData(0.819999999999, "g", "0.819999999999 m")]
        [InlineData(0.819999999999, "F2", "0.82 m")]
        [InlineData(0.819999999999, "G4", "0.82 m")]
        [InlineData(0.8, "G4", "0.8 m")]
        [InlineData(0.00299999999, "G2", "0.003 m")]
        [InlineData(0.00299999999, "G4", "0.003 m")]
        [InlineData(0.0003000001, "e2", "3.00e-004 m")]
        [InlineData(0.0003000001, "e4", "3.0000e-004 m")]
        public void ToString_StandardNumericFormat_RoundsAsSpecified(double value,
            string format, string expected)
        {
            string actual = Length.FromMeters(value).ToString(format, AmericanCulture);
            Assert.Equal(expected, actual);
        }

        [Theory]
        [InlineData(double.MinValue, "-1.80e+308 m")]
        [InlineData(1.23e-120, "1.23e-120 m")]
        [InlineData(0.0000111, "1.11e-005 m")]
        [InlineData(1.99e-4, "1.99e-004 m")]
        public void ToString_ExponentialFormat_BelowMilli(double value, string expected)
        {
            string actual = Length.FromMeters(value).ToString("e2", AmericanCulture);
            Assert.Equal(expected, actual);
        }

        [Theory]
        [InlineData(1e-3, "0.001 m")]
        [InlineData(1.1, "1.1 m")]
        [InlineData(999.99, "999.99 m")]
        public void ToString_CustomFixedPointFormat_BetweenMilliAndKilo(double value, string expected)
        {
            string actual = Length.FromMeters(value).ToString("0.###", AmericanCulture);
            Assert.Equal(expected, actual);
        }

        [Theory]
        [InlineData(1000, "1,000 m")]
        [InlineData(11000, "11,000 m")]
        [InlineData(111000, "111,000 m")]
        [InlineData(999999.99, "999,999.99 m")]
        public void ToString_CustomGroupingFormat_From1e3To1e5(double value, string expected)
        {
            string actual = Length.FromMeters(value).ToString("#,##0.##", AmericanCulture);
            Assert.Equal(expected, actual);
        }

        [Theory]
        [InlineData(1e6, "1e+06 m")]
        [InlineData(11100000, "1.11e+07 m")]
        [InlineData(double.MaxValue, "1.8e+308 m")]
        public void ToString_CustomExponentialFormat_Above1e6(double value, string expected)
        {
            string actual = Length.FromMeters(value).ToString("0.##e+00", AmericanCulture);
            Assert.Equal(expected, actual);
        }

        [Fact]
        public void AllUnitsImplementToStringForInvariantCulture()
        {
            Assert.Equal("1 °", Angle.FromDegrees(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 m²", Area.FromSquareMeters(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 V", ElectricPotential.FromVolts(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 N", Force.FromNewtons(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 m", Length.FromMeters(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 kg", Mass.FromKilograms(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 Pa", Pressure.FromPascals(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 rad/s", RotationalSpeed.FromRadiansPerSecond(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 K", Temperature.FromKelvins(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 N·m", Torque.FromNewtonMeters(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 m³", Volume.FromCubicMeters(1).ToString(CultureInfo.InvariantCulture));
            Assert.Equal("1 m³/s", VolumeFlow.FromCubicMetersPerSecond(1).ToString(CultureInfo.InvariantCulture));

            Assert.Equal("2 ft 3 in", Length.FromFeetInches(2, 3).FeetInches.ToString(CultureInfo.InvariantCulture));
            Assert.Equal("3 st 7 lb", Mass.FromStonePounds(3, 7).StonePounds.ToString(CultureInfo.InvariantCulture));
        }

        [Fact]
        public void ToString_WithNorwegianCulture()
        {
            Assert.Equal("1 °", Angle.FromDegrees(1).ToUnit(AngleUnit.Degree).ToString(NorwegianCulture));
            Assert.Equal("1 m²", Area.FromSquareMeters(1).ToUnit(AreaUnit.SquareMeter).ToString(NorwegianCulture));
            Assert.Equal("1 V", ElectricPotential.FromVolts(1).ToUnit(ElectricPotentialUnit.Volt).ToString(NorwegianCulture));
            Assert.Equal("1 m³/s", VolumeFlow.FromCubicMetersPerSecond(1).ToUnit(VolumeFlowUnit.CubicMeterPerSecond).ToString(NorwegianCulture));
            Assert.Equal("1 N", Force.FromNewtons(1).ToUnit(ForceUnit.Newton).ToString(NorwegianCulture));
            Assert.Equal("1 m", Length.FromMeters(1).ToUnit(LengthUnit.Meter).ToString(NorwegianCulture));
            Assert.Equal("1 kg", Mass.FromKilograms(1).ToUnit(MassUnit.Kilogram).ToString(NorwegianCulture));
            Assert.Equal("1 Pa", Pressure.FromPascals(1).ToUnit(PressureUnit.Pascal).ToString(NorwegianCulture));
            Assert.Equal("1 rad/s", RotationalSpeed.FromRadiansPerSecond(1).ToUnit(RotationalSpeedUnit.RadianPerSecond).ToString(NorwegianCulture));
            Assert.Equal("1 K", Temperature.FromKelvins(1).ToUnit(TemperatureUnit.Kelvin).ToString(NorwegianCulture));
            Assert.Equal("1 N·m", Torque.FromNewtonMeters(1).ToUnit(TorqueUnit.NewtonMeter).ToString(NorwegianCulture));
            Assert.Equal("1 m³", Volume.FromCubicMeters(1).ToUnit(VolumeUnit.CubicMeter).ToString(NorwegianCulture));
        }

        [Fact]
        public void ToString_WithRussianCulture()
        {
            Assert.Equal("1 °", Angle.FromDegrees(1).ToUnit(AngleUnit.Degree).ToString(RussianCulture));
            Assert.Equal("1 м²", Area.FromSquareMeters(1).ToUnit(AreaUnit.SquareMeter).ToString(RussianCulture));
            Assert.Equal("1 В", ElectricPotential.FromVolts(1).ToUnit(ElectricPotentialUnit.Volt).ToString(RussianCulture));
            Assert.Equal("1 м³/с", VolumeFlow.FromCubicMetersPerSecond(1).ToUnit(VolumeFlowUnit.CubicMeterPerSecond).ToString(RussianCulture));
            Assert.Equal("1 Н", Force.FromNewtons(1).ToUnit(ForceUnit.Newton).ToString(RussianCulture));
            Assert.Equal("1 м", Length.FromMeters(1).ToUnit(LengthUnit.Meter).ToString(RussianCulture));
            Assert.Equal("1 кг", Mass.FromKilograms(1).ToUnit(MassUnit.Kilogram).ToString(RussianCulture));
            Assert.Equal("1 Па", Pressure.FromPascals(1).ToUnit(PressureUnit.Pascal).ToString(RussianCulture));
            Assert.Equal("1 рад/с", RotationalSpeed.FromRadiansPerSecond(1).ToUnit(RotationalSpeedUnit.RadianPerSecond).ToString(RussianCulture));
            Assert.Equal("1 K", Temperature.FromKelvins(1).ToUnit(TemperatureUnit.Kelvin).ToString(RussianCulture));
            Assert.Equal("1 Н·м", Torque.FromNewtonMeters(1).ToUnit(TorqueUnit.NewtonMeter).ToString(RussianCulture));
            Assert.Equal("1 м³", Volume.FromCubicMeters(1).ToUnit(VolumeUnit.CubicMeter).ToString(RussianCulture));
        }

    }
}
