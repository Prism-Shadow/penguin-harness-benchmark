package com.mojang.blaze3d.platform;
public class InputConstants {
    public static class Key{
    }
    public enum Type {
        MOUSE;
        public Key getOrCreate(int i){
            return new Key();
        }
    }
}
