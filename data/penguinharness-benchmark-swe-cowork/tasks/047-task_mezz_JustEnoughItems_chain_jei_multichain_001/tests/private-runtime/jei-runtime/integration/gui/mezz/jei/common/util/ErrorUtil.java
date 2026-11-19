package mezz.jei.common.util;
public class ErrorUtil {
    public static void checkNotNull(Object o,String n){
        java.util.Objects.requireNonNull(o,n);
    }
    public static void checkNotEmpty(java.util.Collection<?> c,String n){
        if(c.isEmpty())throw new IllegalArgumentException(n);
    }
}
