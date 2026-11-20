package mezz.jei.api.recipe.category;
public interface IRecipeCategory<T> {
    mezz.jei.api.recipe.types.IRecipeType<T> getRecipeType();
    default boolean needsRecipeBorder(){
        return false;
    }
}
