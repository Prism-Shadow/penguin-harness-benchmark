package mezz.jei.api.gui.builder;
public interface ITooltipBuilder {
    java.util.List<com.mojang.datafixers.util.Either<net.minecraft.network.chat.Component,Object>> getLines();
    void add(Object c);
}
