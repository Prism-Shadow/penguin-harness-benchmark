package mezz.jei.api.recipe;
public interface IFocusGroup {
    java.util.stream.Stream<IFocus<?>> getFocuses(RecipeIngredientRole role);
}
