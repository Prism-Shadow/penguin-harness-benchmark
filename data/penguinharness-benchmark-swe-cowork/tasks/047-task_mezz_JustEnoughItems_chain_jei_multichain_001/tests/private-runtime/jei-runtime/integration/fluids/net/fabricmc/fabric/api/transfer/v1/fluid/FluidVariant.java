package net.fabricmc.fabric.api.transfer.v1.fluid;
public record FluidVariant(boolean isBlank) {
    public static final com.mojang.serialization.Codec<FluidVariant> CODEC=new com.mojang.serialization.Codec<>();
    public static FluidVariant blank(){
        return new FluidVariant(true);
    }
    public static FluidVariant of(net.minecraft.world.level.material.Fluid f,Object... p){
        return new FluidVariant(false);
    }
    public net.minecraft.world.level.material.Fluid getFluid(){
        return new net.minecraft.world.level.material.Fluid();
    }
    public net.minecraft.core.component.DataComponentPatch getComponentsPatch(){
        return net.minecraft.core.component.DataComponentPatch.EMPTY;
    }
}
