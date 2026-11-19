// Licensed under MIT No Attribution, see LICENSE file at the root.
// Copyright 2013 Andreas Gullberg Larsen (andreas.larsen84@gmail.com). Maintained at https://github.com/angularsen/UnitsNet.

namespace UnitsNet.Tests.CustomCode
{
    public class AreaPerLengthTests : AreaPerLengthTestsBase
    {
        protected override double SquareMetersPerMeterInOneSquareMeterPerMeter => 1;
        protected override double SquareCentimetersPerMeterInOneSquareMeterPerMeter => 10000;
        protected override double SquareMillimetersPerMeterInOneSquareMeterPerMeter => 1000000;
        // One international foot is exactly 0.3048 m; one inch is 0.0254 m.
        protected override double SquareFeetPerFootInOneSquareMeterPerMeter => 3.280839895013123;
        protected override double SquareInchesPerFootInOneSquareMeterPerMeter => 472.44094488188976;
        protected override double SquareInchesPerInchInOneSquareMeterPerMeter => 39.37007874015748;
    }
}
