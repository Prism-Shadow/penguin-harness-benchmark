package mezz.jei.common.gui.elements;
public class OffsetDrawable implements mezz.jei.api.gui.drawable.IDrawable {
    public OffsetDrawable(mezz.jei.api.gui.drawable.IDrawable d,int x,int y){
    }
    public static OffsetDrawable create(mezz.jei.api.gui.drawable.IDrawable d,int x,int y){
        return new OffsetDrawable(d,x,y);
    }
    public mezz.jei.common.util.ImmutableRect2i getArea(){
        return mezz.jei.common.util.ImmutableRect2i.EMPTY;
    }
}
