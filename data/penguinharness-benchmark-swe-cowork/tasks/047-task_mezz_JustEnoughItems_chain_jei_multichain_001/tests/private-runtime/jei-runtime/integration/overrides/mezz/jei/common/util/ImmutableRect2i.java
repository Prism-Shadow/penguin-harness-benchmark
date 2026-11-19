package mezz.jei.common.util;
public record ImmutableRect2i(int x,int y,int width,int height) {
    public static final ImmutableRect2i EMPTY=new ImmutableRect2i(0,0,0,0);
    public int getX(){
        return x;
    }
    public int getY(){
        return y;
    }
    public int getWidth(){
        return width;
    }
    public int getHeight(){
        return height;
    }
    public ImmutableRect2i setPosition(int x,int y){
        return new ImmutableRect2i(x,y,width,height);
    }
    public boolean contains(double x,double y){
        return x>=this.x&&y>=this.y&&x<this.x+width&&y<this.y+height;
    }
    public net.minecraft.client.renderer.Rect2i toMutable(){
        return new net.minecraft.client.renderer.Rect2i();
    }
}
