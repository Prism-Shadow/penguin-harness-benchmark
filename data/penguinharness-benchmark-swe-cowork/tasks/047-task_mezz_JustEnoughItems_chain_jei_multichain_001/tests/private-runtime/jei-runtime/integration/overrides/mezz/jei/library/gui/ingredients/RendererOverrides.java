package mezz.jei.library.gui.ingredients;
public class RendererOverrides {
    public <T> void addOverride(mezz.jei.api.ingredients.IIngredientType<T> t,mezz.jei.api.ingredients.IIngredientRenderer<T> r){
    }
    public int getIngredientWidth(){
        return 16;
    }
    public int getIngredientHeight(){
        return 16;
    }
    public <T> java.util.Optional<mezz.jei.api.ingredients.IIngredientRenderer<T>> getIngredientRenderer(mezz.jei.api.ingredients.IIngredientType<T> t){
        return java.util.Optional.empty();
    }
}
