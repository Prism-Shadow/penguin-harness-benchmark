package net.minecraft.client.gui.screens.inventory;
public class AbstractContainerScreen<T extends net.minecraft.world.inventory.AbstractContainerMenu> extends net.minecraft.client.gui.screens.Screen {
    public AbstractContainerScreen(){
        super(net.minecraft.network.chat.Component.literal("parent"));
    }
    public T getMenu(){
        return null;
    }
}
