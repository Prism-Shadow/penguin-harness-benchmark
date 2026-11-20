package mezz.jei.api.gui.builder;
import java.util.*;
import mezz.jei.api.ingredients.*;
import net.minecraft.world.item.crafting.display.SlotDisplay;
import net.minecraft.world.item.*;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.level.material.Fluid;
public interface IIngredientAcceptor<SELF> {
    net.minecraft.util.context.ContextMap getContextMap();
    SELF addIngredientsUnsafe(List<?> v);
    SELF add(SlotDisplay d);
    <I> SELF add(IIngredientType<I> t,SlotDisplay d);
    SELF add(ItemStack s);
    SELF addItemStacks(List<ItemStack> v);
    <T> SELF addIngredients(IIngredientType<T> t,List<T> v);
    SELF add(Ingredient i);
    <I> SELF add(IIngredientType<I> t,Ingredient i);
    <T> SELF add(IIngredientType<T> t,T i);
    <I> SELF add(ITypedIngredient<I> i);
    SELF add(net.minecraft.world.level.ItemLike i);
    SELF add(ItemStackTemplate i);
    SELF add(Fluid f);
    SELF add(Fluid f,long a);
    SELF add(Fluid f,long a,net.minecraft.core.component.DataComponentPatch p);
    SELF addTypedIngredients(List<ITypedIngredient<?>> i);
    SELF addOptionalTypedIngredients(List<Optional<ITypedIngredient<?>>> i);
}
