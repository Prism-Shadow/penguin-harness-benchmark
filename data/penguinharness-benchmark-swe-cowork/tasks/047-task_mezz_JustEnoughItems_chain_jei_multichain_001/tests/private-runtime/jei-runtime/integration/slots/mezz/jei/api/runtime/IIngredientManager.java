package mezz.jei.api.runtime;
public interface IIngredientManager {
    <T> mezz.jei.api.ingredients.IIngredientHelper<T> getIngredientHelper(mezz.jei.api.ingredients.IIngredientType<T> type);
    java.util.Collection<mezz.jei.api.ingredients.IIngredientType<?>> getRegisteredIngredientTypes();
    <T> mezz.jei.api.ingredients.IIngredientType<T> getIngredientType(T ingredient);
}
