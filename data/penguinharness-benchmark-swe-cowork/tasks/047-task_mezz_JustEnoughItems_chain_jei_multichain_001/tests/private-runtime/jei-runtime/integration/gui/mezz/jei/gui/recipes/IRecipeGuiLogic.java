package mezz.jei.gui.recipes;
public interface IRecipeGuiLogic {
    default boolean nextRecipeCategory(){
        return true;
    }
    default boolean previousRecipeCategory(){
        return true;
    }
    default boolean nextPage(){
        return true;
    }
    default boolean previousPage(){
        return true;
    }
    default boolean hasMultipleCategories(){
        return false;
    }
    default boolean hasMultiplePages(){
        return false;
    }
    default void goToFirstPage(){
    }
    default void tick(){
    }
    default void clearHistory(){
    }
    default boolean hasAllCategories(){
        return true;
    }
    default boolean showAllRecipes(){
        return true;
    }
    default boolean showFocus(mezz.jei.api.recipe.IFocusGroup f){
        return true;
    }
    default boolean showCategories(java.util.List<mezz.jei.api.recipe.types.IRecipeType<?>> t){
        return true;
    }
    default boolean showRecipes(mezz.jei.gui.recipes.lookups.IFocusedRecipes<?> r,mezz.jei.api.recipe.IFocusGroup f){
        return true;
    }
    default void back(){
    }
    default void forward(){
    }
    default mezz.jei.api.recipe.category.IRecipeCategory<?> getSelectedRecipeCategory(){
        return null;
    }
    default java.util.List<IRecipeLayoutWithButtons<?>> getVisibleRecipeLayoutsWithButtons(int h,int p,Object menu,Object bookmarks,Object gui){
        return java.util.List.of();
    }
    default int getRecipesPerPage(){
        return 1;
    }
    default String getPageString(){
        return "1/1";
    }
    default java.util.stream.Stream<mezz.jei.api.ingredients.ITypedIngredient<?>> getRecipeCatalysts(){
        return java.util.stream.Stream.empty();
    }
}
