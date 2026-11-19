package mezz.jei.common.gui;
public class RecipeLayoutDrawableErrored<T> implements mezz.jei.api.gui.IRecipeLayoutDrawable<T> {
    public RecipeLayoutDrawableErrored(Object... args){
        throw new AssertionError();
    }
}
