package net.minecraft.network.chat;
public class Component {
    public static Component literal(String s){
        return translatable(s);
    }
    public static Component translatable(String key) {
        return new Component();
    }
}
