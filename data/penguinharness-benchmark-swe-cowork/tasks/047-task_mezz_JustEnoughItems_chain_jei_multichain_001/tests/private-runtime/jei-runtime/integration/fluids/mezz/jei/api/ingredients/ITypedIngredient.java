package mezz.jei.api.ingredients;
public interface ITypedIngredient<T> {
    T getIngredient();
    IIngredientType<T> getType();
    default java.util.Optional<net.minecraft.world.item.ItemStack> getItemStack(){
        return java.util.Optional.empty();
    }
}
