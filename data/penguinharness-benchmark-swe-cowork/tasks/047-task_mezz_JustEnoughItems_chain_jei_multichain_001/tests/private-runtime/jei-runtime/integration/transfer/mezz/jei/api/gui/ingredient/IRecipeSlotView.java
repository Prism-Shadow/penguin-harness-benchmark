package mezz.jei.api.gui.ingredient;
public interface IRecipeSlotView {
    boolean isEmpty();
    java.util.List<mezz.jei.api.ingredients.ITypedIngredient<?>> getAllIngredientsList();
}
