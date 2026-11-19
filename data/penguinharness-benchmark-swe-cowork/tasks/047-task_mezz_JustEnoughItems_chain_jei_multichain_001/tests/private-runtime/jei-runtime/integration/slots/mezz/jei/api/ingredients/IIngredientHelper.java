package mezz.jei.api.ingredients;
public interface IIngredientHelper<T> {
    default String getErrorInfo(T t){
        return String.valueOf(t);
    }
    boolean isValidIngredient(T t);
    default T normalizeIngredient(T t){
        return t;
    }
    default boolean hasSubtypes(T t){
        return false;
    }
    default String getDisplayName(T t){
        return t.toString();
    }
    default java.util.Optional<net.minecraft.world.item.crafting.display.DisplayContentsFactory<T>> getDisplayContentsFactory(){
        return java.util.Optional.of(new net.minecraft.world.item.crafting.display.DisplayContentsFactory<T>(){
        }
        );
    }
    default Object getUid(ITypedIngredient<T> t,mezz.jei.api.ingredients.subtypes.UidContext c){
        return t.getIngredient();
    }
    default Object getGroupingUid(ITypedIngredient<T> t){
        return t.getIngredient();
    }
}
