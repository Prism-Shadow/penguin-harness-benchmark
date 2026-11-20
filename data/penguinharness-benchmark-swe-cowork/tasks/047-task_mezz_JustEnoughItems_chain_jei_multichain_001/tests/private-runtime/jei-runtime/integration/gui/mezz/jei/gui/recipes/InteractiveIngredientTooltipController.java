package mezz.jei.gui.recipes;
public class InteractiveIngredientTooltipController implements mezz.jei.gui.input.IGuiInputLayer {
    public InteractiveIngredientTooltipController(Object... args){
    }
    public void hide(){
    }
    public boolean isVisible(){
        return false;
    }
    public boolean show(Object slot,Object target,double x,double y){
        return false;
    }
    public java.util.stream.Stream<mezz.jei.gui.input.IClickableIngredientInternal<?>> getIngredientUnderMouse(double x,double y){
        return java.util.stream.Stream.empty();
    }
}
