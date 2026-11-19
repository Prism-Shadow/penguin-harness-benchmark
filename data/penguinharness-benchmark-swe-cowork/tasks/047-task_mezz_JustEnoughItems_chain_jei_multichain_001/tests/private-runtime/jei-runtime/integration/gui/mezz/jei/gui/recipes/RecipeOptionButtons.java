package mezz.jei.gui.recipes;
public class RecipeOptionButtons {
    public RecipeOptionButtons(Runnable r){
    }
    public int getWidth(){
        return 0;
    }
    public mezz.jei.common.util.ImmutableRect2i getArea(){
        return mezz.jei.common.util.ImmutableRect2i.EMPTY;
    }
    public void updateLayout(Object a){
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
