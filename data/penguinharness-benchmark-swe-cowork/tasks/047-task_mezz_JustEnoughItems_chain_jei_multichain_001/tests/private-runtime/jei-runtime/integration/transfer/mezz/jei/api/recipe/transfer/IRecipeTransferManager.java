package mezz.jei.api.recipe.transfer;
public interface IRecipeTransferManager {
    <C extends net.minecraft.world.inventory.AbstractContainerMenu,R> java.util.Optional<IRecipeTransferHandler<C,R>> getRecipeTransferHandler(C c,mezz.jei.api.recipe.category.IRecipeCategory<R> r);
}
