using System;

public static class WrapperFixture<T>
{
    public static int Calls;
    private static int stored;
    public static int Value { get { Calls++; return stored; } set { Calls++; stored = value; } }
    public static int Route(int value) { Calls++; return value * 3 + (typeof(T) == typeof(int) ? 7 : 19); }
    public static int Route(bool value) { Calls++; return value ? 41 : -23; }
    public static int Branch(bool positive, int value)
    {
        Calls++;
        if (value == -999) throw new InvalidOperationException("wrapper-branch-error");
        if (positive) { int local = value + 5; return local * 2; }
        return value - 11;
    }
}
