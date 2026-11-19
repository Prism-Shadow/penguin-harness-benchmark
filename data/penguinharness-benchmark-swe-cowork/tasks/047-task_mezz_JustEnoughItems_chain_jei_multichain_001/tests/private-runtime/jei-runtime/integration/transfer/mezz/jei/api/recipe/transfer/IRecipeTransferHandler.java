package mezz.jei.api.recipe.transfer;
public interface IRecipeTransferHandler<C,R> {
    IRecipeTransferError transferRecipe(C c,R r,mezz.jei.api.gui.ingredient.IRecipeSlotsView v,net.minecraft.world.entity.player.Player p,boolean max,boolean perform);
    Class<C> getContainerClass();
}
