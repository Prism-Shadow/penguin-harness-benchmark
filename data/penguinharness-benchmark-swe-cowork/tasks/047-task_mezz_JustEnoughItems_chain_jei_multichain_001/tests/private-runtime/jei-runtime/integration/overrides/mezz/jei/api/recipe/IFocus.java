package mezz.jei.api.recipe;
public interface IFocus<T> {
    mezz.jei.api.ingredients.ITypedIngredient<T> getTypedValue();
}
