package com.mojang.datafixers.util;
public record Either<L,R>(L l,R r) {
    public static <L,R> Either<L,R> left(L value){
        return new Either<>(value,null);
    }
}
