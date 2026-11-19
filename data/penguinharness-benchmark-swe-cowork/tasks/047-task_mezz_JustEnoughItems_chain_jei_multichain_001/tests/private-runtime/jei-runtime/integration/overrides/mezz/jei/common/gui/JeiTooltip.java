package mezz.jei.common.gui;
public class JeiTooltip implements mezz.jei.api.gui.builder.ITooltipBuilder {
    public java.util.List<com.mojang.datafixers.util.Either<net.minecraft.network.chat.Component,Object>> getLines(){
        return new java.util.ArrayList<>();
    }
    public void add(Object c){
    }
    public java.util.List<net.minecraft.network.chat.Component> getLegacyComponents(){
        return java.util.List.of();
    }
    public void draw(Object g,int x,int y){
    }
}
