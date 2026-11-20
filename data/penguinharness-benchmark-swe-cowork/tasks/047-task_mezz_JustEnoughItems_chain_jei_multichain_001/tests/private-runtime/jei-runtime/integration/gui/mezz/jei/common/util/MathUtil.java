package mezz.jei.common.util;
public class MathUtil {
    public static ImmutableRect2i union(ImmutableRect2i a,ImmutableRect2i b){
        int x=Math.min(a.x(),b.x()),y=Math.min(a.y(),b.y());
        return new ImmutableRect2i(x,y,Math.max(a.x()+a.width(),b.x()+b.width())-x,Math.max(a.y()+a.height(),b.y()+b.height())-y);
    }
}
