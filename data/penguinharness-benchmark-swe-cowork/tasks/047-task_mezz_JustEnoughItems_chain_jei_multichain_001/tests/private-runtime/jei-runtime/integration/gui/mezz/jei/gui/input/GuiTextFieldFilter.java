package mezz.jei.gui.input;
public class GuiTextFieldFilter implements mezz.jei.gui.overlay.ISearchField {
    public static GuiTextFieldFilter last;
    public mezz.jei.common.util.ImmutableRect2i area;
    public int updates;
    private boolean focused;
    public GuiTextFieldFilter(java.util.function.BooleanSupplier empty){
        last=this;
    }
    public void setValue(String value){
    }
    public void setFocused(boolean b){
        focused=b;
    }
    public boolean isFocused(){
        return focused;
    }
    public void updateBounds(mezz.jei.common.util.ImmutableRect2i area){
        this.area=area;
        updates++;
    }
    public void setResponder(java.util.function.Consumer<String> c){
    }
    public IUserInputHandler createInputHandler(){
        return new IUserInputHandler(){
        }
        ;
    }
    public boolean charTyped(net.minecraft.client.input.CharacterEvent e){
        return false;
    }
    public void extractRenderState(Object g,int x,int y,float t){
    }
    public void extractBackgroundRenderState(Object g){
    }
    public void extractForegroundRenderState(Object g,int x,int y,float a){
    }
}
