package mezz.jei.library.ingredients;
public interface IIngredientManagerInternal extends mezz.jei.api.runtime.IIngredientManager {
    <T> java.util.List<mezz.jei.api.ingredients.ITypedIngredient<T>> getGroupedIngredients(mezz.jei.api.ingredients.ITypedIngredient<T> ingredient);
    java.util.stream.Stream<SlotIngredient<?>> resolveSlotDisplay(net.minecraft.util.context.ContextMap c,mezz.jei.api.recipe.RecipeIngredientRole r,net.minecraft.world.item.crafting.display.SlotDisplay d);
    <T> java.util.stream.Stream<SlotIngredient<T>> resolveSlotDisplay(mezz.jei.api.ingredients.IIngredientType<T> t,net.minecraft.util.context.ContextMap c,mezz.jei.api.recipe.RecipeIngredientRole r,net.minecraft.world.item.crafting.display.SlotDisplay d);
}
