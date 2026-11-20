package mezz.jei.gui.input;
public interface IRecipeFocusSource {
    java.util.stream.Stream<IClickableIngredientInternal<?>> getIngredientUnderMouse(double x,double y);
    java.util.stream.Stream<IDraggableIngredientInternal<?>> getDraggableIngredientUnderMouse(double x,double y);
}
