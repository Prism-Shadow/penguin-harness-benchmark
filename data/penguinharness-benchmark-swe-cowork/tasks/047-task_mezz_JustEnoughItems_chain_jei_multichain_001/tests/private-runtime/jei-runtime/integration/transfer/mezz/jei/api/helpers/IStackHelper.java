package mezz.jei.api.helpers;
public interface IStackHelper {
    Object getUidForStack(net.minecraft.world.item.ItemStack s,mezz.jei.api.ingredients.subtypes.UidContext c);
    Object getUidForStack(mezz.jei.api.ingredients.ITypedIngredient<net.minecraft.world.item.ItemStack> s,mezz.jei.api.ingredients.subtypes.UidContext c);
}
