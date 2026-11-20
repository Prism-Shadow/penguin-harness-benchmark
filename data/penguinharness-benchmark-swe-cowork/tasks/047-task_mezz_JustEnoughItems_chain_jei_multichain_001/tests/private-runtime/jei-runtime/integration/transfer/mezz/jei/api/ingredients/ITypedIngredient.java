package mezz.jei.api.ingredients;
public interface ITypedIngredient<T> {
    T getIngredient();
    ITypedIngredient<net.minecraft.world.item.ItemStack> castToItemStackType();
}
