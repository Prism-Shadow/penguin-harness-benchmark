package net.minecraft.world.level.material;
public class Fluid {
    public Object defaultFluidState(){
        return this;
    }
    public boolean isSource(Object state){
        return true;
    }
    public boolean isSame(Fluid f){
        return this==f;
    }
    public net.minecraft.core.Holder<Fluid> builtInRegistryHolder(){
        return new net.minecraft.core.Holder<>(this);
    }
}
