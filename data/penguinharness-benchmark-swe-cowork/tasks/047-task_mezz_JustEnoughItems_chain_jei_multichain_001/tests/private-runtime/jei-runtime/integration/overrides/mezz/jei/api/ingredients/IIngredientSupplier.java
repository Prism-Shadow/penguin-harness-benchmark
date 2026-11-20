package mezz.jei.api.ingredients;
public interface IIngredientSupplier {
    java.util.List<ITypedIngredient<?>> getIngredients(mezz.jei.api.recipe.RecipeIngredientRole role);
}
