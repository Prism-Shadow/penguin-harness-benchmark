package net.fabricmc.fabric.api.transfer.v1.storage;
public interface Storage<T> extends Iterable<Storage.View<T>> {
    interface View<T> {
        T getResource();
        long getAmount();
    }
}
