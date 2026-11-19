package mezz.jei.gui.elements;
public class IconButton {
    private mezz.jei.common.util.ImmutableRect2i area=new mezz.jei.common.util.ImmutableRect2i(0,0,20,20);
    public IconButton(Object controller){
    }
    public IconButton(Object controller,mezz.jei.common.util.ImmutableRect2i r){
        area=r;
    }
    public void updateBounds(mezz.jei.common.util.ImmutableRect2i r){
        area=r;
    }
    public mezz.jei.common.util.ImmutableRect2i getArea(){
        return area;
    }
    public int getX(){
        return area.x();
    }
    public int getY(){
        return area.y();
    }
    public int getWidth(){
        return area.width();
    }
    public int getHeight(){
        return area.height();
    }
    public void tick(){
    }
    public void draw(Object g,int x,int y,float t){
    }
    public void drawTooltips(Object g,int x,int y){
    }
    public mezz.jei.gui.input.IUserInputHandler createInputHandler(){
        return new mezz.jei.gui.input.IUserInputHandler(){
        }
        ;
    }
}
