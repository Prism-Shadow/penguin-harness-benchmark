package mezz.jei.api.runtime;
public interface IIngredientManager {
    default <T> mezz.jei.api.ingredients.ITypedIngredient<T> normalizeTypedIngredient(mezz.jei.api.ingredients.ITypedIngredient<T> t){
        return t.normalize(getIngredientHelper(t.getType()));
    }
    default <T> mezz.jei.api.ingredients.IIngredientRenderer<T> getIngredientRenderer(mezz.jei.api.ingredients.IIngredientType<T> t){
        throw new AssertionError();
    }
    <T> mezz.jei.api.ingredients.IIngredientHelper<T> getIngredientHelper(mezz.jei.api.ingredients.IIngredientType<T> type);
    java.util.Collection<mezz.jei.api.ingredients.IIngredientType<?>> getRegisteredIngredientTypes();
    <T> mezz.jei.api.ingredients.IIngredientType<T> getIngredientType(T ingredient);
}
