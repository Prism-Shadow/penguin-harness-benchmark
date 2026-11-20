package mezz.jei.api.gui;
public interface IRecipeLayoutDrawable<R> {
    mezz.jei.api.recipe.category.IRecipeCategory<R> getRecipeCategory();
    mezz.jei.api.gui.ingredient.IRecipeSlotsView getRecipeSlotsView();
    R getRecipe();
}
