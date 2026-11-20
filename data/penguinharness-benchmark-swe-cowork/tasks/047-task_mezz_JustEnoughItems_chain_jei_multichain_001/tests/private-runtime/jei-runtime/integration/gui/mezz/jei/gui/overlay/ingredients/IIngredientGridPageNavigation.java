package mezz.jei.gui.overlay.ingredients;
public interface IIngredientGridPageNavigation {
    mezz.jei.gui.overlay.elements.IElement<?> getPageAnchorElement();
    void updateLayoutKeepingPageAnchorVisible(mezz.jei.gui.overlay.elements.IElement<?> e);
    void updateLayoutToFirstPage();
}
