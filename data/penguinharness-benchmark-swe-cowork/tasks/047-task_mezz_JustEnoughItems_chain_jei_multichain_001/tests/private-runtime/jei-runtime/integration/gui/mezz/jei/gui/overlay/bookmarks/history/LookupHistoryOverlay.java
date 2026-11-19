package mezz.jei.gui.overlay.bookmarks.history;
public class LookupHistoryOverlay extends mezz.jei.gui.overlay.ingredients.IIngredientListOverlayContents implements ILookupHistoryOverlay {
    public static final int SLOT_HEIGHT=18;
    public boolean isDisplayedOnThisSide(){
        return false;
    }
    public int getDisplayHeight(){
        return 0;
    }
    public void updateLayout(){
    }
    public boolean isListDisplayed(){
        return false;
    }
    public void draw(Object m,Object g,int x,int y,float t){
    }
}
