using ComputeSharp;
using ComputeSharp.D2D1;
using ComputeSharp.D2D1.Interop;

public partial class OuterClass
{
    public partial record OuterRecord
    {
        public partial struct OuterStruct
        {
            public partial record struct OuterRecordStruct
            {
                public partial interface IContainer
                {
                    [D2DInputCount(0)]
                    [D2DGeneratedPixelShaderDescriptor]
                    [AutoConstructor]
                    public readonly partial struct DeeplyNestedShader : ID2D1PixelShader
                    {
                        public Float4 Execute() => 0;
                    }
                }
            }
        }
    }
}

public static class Program
{
    public static int Main()
    {
        int count = D2D1PixelShader.GetInputCount<OuterClass.OuterRecord.OuterStruct.OuterRecordStruct.IContainer.DeeplyNestedShader>();

        if (count != 0)
        {
            Console.Error.WriteLine($"deeply nested descriptor reported {count} inputs");
            return 1;
        }

        Console.WriteLine("PASS PR 589: deeply nested partial record-struct descriptor compiled and executed");
        return 0;
    }
}
