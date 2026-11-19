package net.minecraft.network.chat;
public record Component(String text, java.util.List<net.minecraft.ChatFormatting> style) {
    public static Component literal(String s){
        return new Component(s,java.util.List.of());
    }
    public static Component translatable(String s,Object... a){
        return literal(s+java.util.Arrays.toString(a));
    }
    public Component withStyle(net.minecraft.ChatFormatting f){
        var l=new java.util.ArrayList<>(style);
        l.add(f);
        return new Component(text,java.util.List.copyOf(l));
    }
    public String getString(){
        return text;
    }
}
