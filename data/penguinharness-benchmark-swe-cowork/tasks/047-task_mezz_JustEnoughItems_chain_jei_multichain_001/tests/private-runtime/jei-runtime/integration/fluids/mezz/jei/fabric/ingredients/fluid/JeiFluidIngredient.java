package mezz.jei.fabric.ingredients.fluid;
public record JeiFluidIngredient(net.fabricmc.fabric.api.transfer.v1.fluid.FluidVariant variant,long amount) implements mezz.jei.api.fabric.ingredients.fluids.IJeiFluidIngredient {
    public long getAmount(){
        return amount;
    }
    public net.fabricmc.fabric.api.transfer.v1.fluid.FluidVariant getFluidVariant(){
        return variant;
    }
}
