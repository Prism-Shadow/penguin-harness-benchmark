package mezz.jei.api.gui;
public interface IRecipeLayoutDrawable<T> {
    void drawOverlays(Object g,int x,int y);
    java.util.Optional<mezz.jei.api.gui.ingredient.IRecipeSlotDrawable> getSlotUnderMouse(double x,double y);
}
