package mezz.jei.library.recipes;
public class RecipeManagerInternal {
    public <T> mezz.jei.api.recipe.category.IRecipeCategory<T> getRecipeCategory(mezz.jei.api.recipe.types.IRecipeType<T> type){
        throw new AssertionError();
    }
    public <T> void addRecipes(mezz.jei.api.recipe.types.IRecipeType<T> t,java.util.List<T> r,Object c){
        throw new AssertionError();
    }
    public <T> void hideRecipes(mezz.jei.api.recipe.types.IRecipeType<T> t,java.util.Collection<T> r){
        throw new AssertionError();
    }
    public <T> void unhideRecipes(mezz.jei.api.recipe.types.IRecipeType<T> t,java.util.Collection<T> r){
        throw new AssertionError();
    }
    public void hideRecipeCategory(Object t){
        throw new AssertionError();
    }
    public void unhideRecipeCategory(Object t){
        throw new AssertionError();
    }
    public <T> java.util.Optional<mezz.jei.api.recipe.types.IRecipeType<T>> getRecipeType(net.minecraft.resources.Identifier id,Class<? extends T> t){
        throw new AssertionError();
    }
    public java.util.Optional<mezz.jei.api.recipe.types.IRecipeType<?>> getRecipeType(net.minecraft.resources.Identifier id){
        throw new AssertionError();
    }
}
