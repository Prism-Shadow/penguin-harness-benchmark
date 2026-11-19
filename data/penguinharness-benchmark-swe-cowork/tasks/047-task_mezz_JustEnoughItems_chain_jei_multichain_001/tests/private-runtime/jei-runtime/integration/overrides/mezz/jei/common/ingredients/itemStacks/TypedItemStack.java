package mezz.jei.common.ingredients.itemStacks;
public class TypedItemStack {
    public static mezz.jei.api.ingredients.ITypedIngredient<net.minecraft.world.item.ItemStack> create(Object value){
        throw new AssertionError("String-only fixture entered item path");
    }
}
