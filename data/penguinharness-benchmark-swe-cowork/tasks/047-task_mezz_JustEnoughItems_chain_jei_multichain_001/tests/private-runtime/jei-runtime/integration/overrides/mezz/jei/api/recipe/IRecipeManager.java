package mezz.jei.api.recipe;
import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableListMultimap;
import mezz.jei.api.gui.IRecipeLayoutDrawable;
import mezz.jei.api.gui.drawable.IScalableDrawable;
import mezz.jei.api.gui.ingredient.IRecipeSlotDrawable;
import mezz.jei.api.ingredients.IIngredientSupplier;
import mezz.jei.api.ingredients.ITypedIngredient;
import mezz.jei.api.recipe.ICraftingStationLookup;
import mezz.jei.api.recipe.IFocusGroup;
import mezz.jei.api.recipe.IRecipeCategoriesLookup;
import mezz.jei.api.recipe.IRecipeLookup;
import mezz.jei.api.recipe.IRecipeManager;
import mezz.jei.api.recipe.RecipeIngredientRole;
import mezz.jei.api.recipe.advanced.IRecipeButtonControllerFactory;
import mezz.jei.api.recipe.category.IRecipeCategory;
import mezz.jei.api.recipe.category.extensions.IRecipeCategoryDecorator;
import mezz.jei.api.recipe.types.IRecipeType;
import mezz.jei.common.Internal;
import mezz.jei.common.gui.RecipeLayoutDrawableErrored;
import mezz.jei.common.gui.elements.DrawableBlank;
import mezz.jei.common.util.ErrorUtil;
import mezz.jei.library.gui.ingredients.CycleTimer;
import mezz.jei.library.focus.FocusGroup;
import mezz.jei.library.gui.recipes.RecipeLayout;
import mezz.jei.library.gui.recipes.layout.builder.RecipeSlotBuilder;
import mezz.jei.library.ingredients.IIngredientManagerInternal;
import mezz.jei.library.util.IngredientSupplierHelper;
import net.minecraft.resources.Identifier;
import net.minecraft.util.context.ContextMap;
import org.jetbrains.annotations.Unmodifiable;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Set;
public interface IRecipeManager {
    <R> IRecipeLookup<R> createRecipeLookup(IRecipeType<R> recipeType);
    IRecipeCategoriesLookup createRecipeCategoryLookup();
    <T> IRecipeCategory<T> getRecipeCategory(IRecipeType<T> recipeType);
    mezz.jei.api.recipe.IRecipeCatalystLookup createRecipeCatalystLookup(IRecipeType<?> recipeType);
    ICraftingStationLookup createCraftingStationLookup(IRecipeType<?> recipeType);
    <T> void addRecipes(IRecipeType<T> recipeType, List<T> recipes);
    <T> IRecipeLayoutDrawable<T> createRecipeLayoutDrawableOrShowError(IRecipeCategory<T> recipeCategory, T recipe, IFocusGroup focusGroup);
    <T> Optional<IRecipeLayoutDrawable<T>> createRecipeLayoutDrawable(IRecipeCategory<T> recipeCategory, T recipe, IFocusGroup focusGroup);
    <T> Optional<IRecipeLayoutDrawable<T>> createRecipeLayoutDrawable(
    IRecipeCategory<T> recipeCategory,
    T recipe,
    IFocusGroup focusGroup,
    IScalableDrawable background,
    int borderSize
    );
    IRecipeSlotDrawable createRecipeSlotDrawable(RecipeIngredientRole role, List<Optional<ITypedIngredient<?>>> ingredients, Set<Integer> focusedIngredients, int ingredientCycleOffset);
    <T> IIngredientSupplier getRecipeIngredients(IRecipeCategory<T> recipeCategory, T recipe);
    <T> void hideRecipes(IRecipeType<T> recipeType, Collection<T> recipes);
    <T> void unhideRecipes(IRecipeType<T> recipeType, Collection<T> recipes);
    void hideRecipeCategory(IRecipeType<?> recipeType);
    void unhideRecipeCategory(IRecipeType<?> recipeType);
    <T> Optional<IRecipeType<T>> getRecipeType(Identifier recipeUid, Class<? extends T> recipeClass);
    Optional<IRecipeType<?>> getRecipeType(Identifier recipeUid);
    List<IRecipeButtonControllerFactory> getRecipeButtonControllerFactories();
}
