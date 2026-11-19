package net.minecraft.client;
public class Minecraft {
    private static final Minecraft INSTANCE=new Minecraft();
    public static Minecraft getInstance(){
        return INSTANCE;
    }
    public final Gui gui=new Gui();
    public final Options options=new Options();
    public boolean hasShiftDown(){
        return false;
    }
    public static class Options {
        public Object keyInventory;
    }
    public static class Gui {
        private net.minecraft.client.gui.screens.Screen screen;
        public int changes;
        public net.minecraft.client.gui.screens.Screen screen(){
            return screen;
        }
        public void setScreen(net.minecraft.client.gui.screens.Screen screen){
            this.screen=screen;
            changes++;
            if(screen!=null)screen.init();
        }
    }
}
