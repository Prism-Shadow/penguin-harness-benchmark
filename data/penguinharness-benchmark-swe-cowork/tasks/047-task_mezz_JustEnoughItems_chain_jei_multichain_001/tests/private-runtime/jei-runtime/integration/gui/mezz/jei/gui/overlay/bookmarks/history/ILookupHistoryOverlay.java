package mezz.jei.gui.overlay.bookmarks.history;
public interface ILookupHistoryOverlay {
    boolean isDisplayedOnThisSide();
    int getDisplayHeight();
    void close();
    void updateBounds(mezz.jei.common.util.ImmutableRect2i a,java.util.Set<mezz.jei.common.util.ImmutableRect2i> e,mezz.jei.common.util.ImmutablePoint2i p);
    void updateLayout();
}
