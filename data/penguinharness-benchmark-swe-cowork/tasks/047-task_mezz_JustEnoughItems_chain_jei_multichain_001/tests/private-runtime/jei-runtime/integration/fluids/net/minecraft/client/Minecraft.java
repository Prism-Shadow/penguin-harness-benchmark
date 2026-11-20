package net.minecraft.client;
public class Minecraft {
    public static Minecraft getInstance(){
        throw new AssertionError("rendering must not initialize");
    }
    public net.minecraft.client.resources.model.ModelManager getModelManager(){
        throw new AssertionError();
    }
}
