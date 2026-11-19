package net.minecraft.tags;
public record TagKey<T>(String name) {
    public Registry registry(){
        return new Registry();
    }
    public static class Registry {
        public net.minecraft.resources.Identifier identifier(){
            return new net.minecraft.resources.Identifier("tag");
        }
    }
}
