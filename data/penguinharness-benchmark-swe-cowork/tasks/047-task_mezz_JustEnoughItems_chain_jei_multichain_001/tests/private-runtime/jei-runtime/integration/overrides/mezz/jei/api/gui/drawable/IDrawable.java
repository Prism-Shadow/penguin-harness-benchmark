package mezz.jei.api.gui.drawable;
public interface IDrawable {
    default void draw(net.minecraft.client.gui.GuiGraphicsExtractor g,int x,int y){
    }
    default int getWidth(){
        return 16;
    }
    default int getHeight(){
        return 16;
    }
}
