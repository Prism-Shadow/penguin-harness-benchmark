package mezz.jei.common.util;
public class ErrorUtil {
    public static <T> T checkNotNull(T value,String name){
        return java.util.Objects.requireNonNull(value,name);
    }
}
