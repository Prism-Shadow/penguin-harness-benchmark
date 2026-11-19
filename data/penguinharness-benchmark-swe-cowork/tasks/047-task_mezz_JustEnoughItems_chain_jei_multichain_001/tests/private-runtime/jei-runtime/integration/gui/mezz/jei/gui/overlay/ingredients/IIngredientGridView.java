package mezz.jei.gui.overlay.ingredients;
public interface IIngredientGridView {
    boolean hasRoom();
    void close();
    void updateBounds(mezz.jei.common.util.ImmutableRect2i area,java.util.Set<mezz.jei.common.util.ImmutableRect2i> exclusions,mezz.jei.common.util.ImmutablePoint2i mouse);
    mezz.jei.common.util.ImmutableRect2i getBackgroundArea();
}
