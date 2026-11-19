package mezz.jei.api.ingredients;
public interface ITypedIngredient<T> {
    T getIngredient();
    default <V> java.util.Optional<V> getIngredient(IIngredientType<V> t){
        return java.util.Optional.ofNullable(t.getCastIngredient(getIngredient()));
    }
    IIngredientType<T> getType();
    default java.util.Optional<net.minecraft.world.item.ItemStack> getItemStack(){
        return java.util.Optional.empty();
    }
}
