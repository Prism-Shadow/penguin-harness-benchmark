package mezz.jei.gui.overlay.ingredients;
public class IIngredientListOverlayContents implements IIngredientGridView,IIngredientGridPageNavigation {
    private mezz.jei.common.util.ImmutableRect2i area;
    public boolean isEmpty(){
        return false;
    }
    public boolean hasRoom(){
        return true;
    }
    public void close(){
    }
    public void updateBounds(mezz.jei.common.util.ImmutableRect2i a,java.util.Set<mezz.jei.common.util.ImmutableRect2i> e,mezz.jei.common.util.ImmutablePoint2i p){
        area=a;
    }
    public mezz.jei.common.util.ImmutableRect2i getBackgroundArea(){
        return area;
    }
    public mezz.jei.gui.overlay.elements.IElement<?> getPageAnchorElement(){
        return null;
    }
    public void updateLayoutKeepingPageAnchorVisible(mezz.jei.gui.overlay.elements.IElement<?> e){
    }
    public void updateLayoutToFirstPage(){
    }
    public void tick(){
    }
    public void drawBackground(Object g){
    }
    public void drawForeground(Object m,Object g,int x,int y,float t){
    }
    public void drawTooltips(Object m,Object g,int x,int y){
    }
    public void drawOnForeground(Object g,int x,int y){
    }
    public java.util.stream.Stream<mezz.jei.gui.input.IClickableIngredientInternal<?>> getIngredientUnderMouse(double x,double y){
        return java.util.stream.Stream.empty();
    }
    public java.util.stream.Stream<mezz.jei.gui.input.IDraggableIngredientInternal<?>> getDraggableIngredientUnderMouse(double x,double y){
        return java.util.stream.Stream.empty();
    }
    public mezz.jei.gui.input.IUserInputHandler createInputHandler(){
        return new mezz.jei.gui.input.IUserInputHandler(){
        }
        ;
    }
    public mezz.jei.gui.input.IDragHandler createDragHandler(){
        return new mezz.jei.gui.input.IDragHandler(){
        }
        ;
    }
    public <T> java.util.stream.Stream<T> getVisibleIngredients(mezz.jei.api.ingredients.IIngredientType<T> t){
        return java.util.stream.Stream.empty();
    }
}
