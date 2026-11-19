package mezz.jei.gui.recipes;
public class CraftingStations {
    public CraftingStations(Object m){
    }
    public boolean isEmpty(){
        return true;
    }
    public int getWidth(){
        return 0;
    }
    public void updateLayout(Object ingredients,Object area,Object buttons){
    }
    public java.util.Optional<mezz.jei.api.gui.ingredient.IRecipeSlotDrawable> draw(Object g,int x,int y){
        return java.util.Optional.empty();
    }
    public java.util.stream.Stream<mezz.jei.gui.input.IClickableIngredientInternal<?>> getIngredientUnderMouse(double x,double y){
        return java.util.stream.Stream.empty();
    }
}
