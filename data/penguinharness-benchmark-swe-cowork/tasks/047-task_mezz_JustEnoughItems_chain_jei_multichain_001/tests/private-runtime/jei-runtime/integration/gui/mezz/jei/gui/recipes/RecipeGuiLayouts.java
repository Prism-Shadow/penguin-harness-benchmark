package mezz.jei.gui.recipes;
public class RecipeGuiLayouts {
    public RecipeGuiLayouts(Object... f){
    }
    public mezz.jei.gui.input.IUserInputHandler createInputHandler(){
        return new mezz.jei.gui.input.IUserInputHandler(){
        }
        ;
    }
    public void tick(){
    }
    public int getWidth(){
        return 0;
    }
    public void setRecipeLayoutsWithButtons(java.util.List<IRecipeLayoutWithButtons<?>> l){
    }
    public void updateLayout(Object area,int perPage){
    }
    public java.util.Optional<mezz.jei.api.gui.IRecipeLayoutDrawable<?>> draw(Object g,int x,int y){
        return java.util.Optional.empty();
    }
    public void drawTooltips(Object g,int x,int y){
    }
    public java.util.stream.Stream<mezz.jei.gui.input.IClickableIngredientInternal<?>> getIngredientUnderMouse(double x,double y){
        return java.util.stream.Stream.empty();
    }
    public void mouseMoved(double x,double y){
    }
    public boolean mouseDragged(double x,double y,Object input,double dx,double dy){
        return false;
    }
    public java.util.Optional<IRecipeLayoutWithButtons<?>> getRecipeLayoutUnderMouse(double x,double y){
        return java.util.Optional.empty();
    }
}
