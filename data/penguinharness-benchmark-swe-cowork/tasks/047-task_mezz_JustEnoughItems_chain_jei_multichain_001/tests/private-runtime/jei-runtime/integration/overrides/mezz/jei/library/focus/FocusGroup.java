package mezz.jei.library.focus;
public class FocusGroup {
    public static mezz.jei.api.recipe.IFocusGroup checkOne(mezz.jei.api.recipe.IFocusGroup f,Object m){
        return f;
    }
    public static final mezz.jei.api.recipe.IFocusGroup EMPTY=r->java.util.stream.Stream.empty();
}
