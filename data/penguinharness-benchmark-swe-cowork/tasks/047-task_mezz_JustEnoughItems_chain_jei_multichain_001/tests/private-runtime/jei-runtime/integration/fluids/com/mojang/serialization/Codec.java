package com.mojang.serialization;
public class Codec<T> {
    public static <T> Codec<T> lazyInitialized(java.util.function.Supplier<Codec<T>> s){
        return new Codec<>();
    }
    public <U> Codec<U> xmap(java.util.function.Function<T,U> a, java.util.function.Function<U,T> b){
        return new Codec<>();
    }
}
