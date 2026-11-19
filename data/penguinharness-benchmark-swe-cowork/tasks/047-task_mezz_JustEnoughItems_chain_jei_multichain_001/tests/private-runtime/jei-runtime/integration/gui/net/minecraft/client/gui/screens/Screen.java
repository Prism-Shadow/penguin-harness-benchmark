package net.minecraft.client.gui.screens;
public class Screen {
    public net.minecraft.client.Minecraft minecraft=net.minecraft.client.Minecraft.getInstance();
    public net.minecraft.client.gui.Font font=new net.minecraft.client.gui.Font();
    public int width=800,height=600;
    public Screen(net.minecraft.network.chat.Component title){
    }
    public void init(){
    }
    public boolean isPauseScreen(){
        return false;
    }
    public boolean isInGameUi(){
        return true;
    }
    public void extractBackground(net.minecraft.client.gui.GuiGraphicsExtractor g,int x,int y,float a){
    }
    public void extractRenderState(net.minecraft.client.gui.GuiGraphicsExtractor g,int x,int y,float a){
    }
    public void tick(){
    }
    public boolean isMouseOver(double x,double y){
        return false;
    }
    public void mouseMoved(double x,double y){
    }
    public boolean mouseDragged(net.minecraft.client.input.MouseButtonEvent e,double x,double y){
        return false;
    }
    public boolean mouseScrolled(double x,double y,double dx,double dy){
        return false;
    }
    public boolean mouseClicked(net.minecraft.client.input.MouseButtonEvent e,boolean twice){
        return false;
    }
    public boolean mouseReleased(net.minecraft.client.input.MouseButtonEvent e){
        return false;
    }
    public boolean keyPressed(net.minecraft.client.input.KeyEvent e){
        return false;
    }
    public void onClose(){
    }
}
