package mezz.jei.common.platform;
public interface IPlatformFluidHelperInternal<T> {
    long bucketVolume();
    T create(net.minecraft.core.Holder<net.minecraft.world.level.material.Fluid> f,long a,net.minecraft.core.component.DataComponentPatch p);
    mezz.jei.api.ingredients.IIngredientTypeWithSubtypes<net.minecraft.world.level.material.Fluid,T> getFluidIngredientType();
}
