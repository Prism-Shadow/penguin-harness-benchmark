package mezz.jei.api.fabric.ingredients.fluids;
public interface IJeiFluidIngredient {
    long getAmount();
    net.fabricmc.fabric.api.transfer.v1.fluid.FluidVariant getFluidVariant();
}
