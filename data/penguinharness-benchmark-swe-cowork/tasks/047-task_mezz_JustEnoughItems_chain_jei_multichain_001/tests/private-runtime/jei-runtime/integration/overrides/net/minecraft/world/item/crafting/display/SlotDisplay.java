package net.minecraft.world.item.crafting.display;
public interface SlotDisplay {
    Type<? extends SlotDisplay> type();
    <T> java.util.stream.Stream<T> resolve(net.minecraft.util.context.ContextMap c,DisplayContentsFactory<T> f);
    class Type<D extends SlotDisplay> {
    }
}
