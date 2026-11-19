package mezz.jei.common.util;
public class ErrorUtil {
    public static void checkNotEmpty(java.util.Collection<?> c,String n){
        if(c.isEmpty())throw new IllegalArgumentException(n);
    }
    public static void validateRecipes(Object t,Object r){
    }
    public static void assertMainThread(){
    }
    public static <T> T checkNotNull(T value,String name){
        return java.util.Objects.requireNonNull(value,name);
    }
}
