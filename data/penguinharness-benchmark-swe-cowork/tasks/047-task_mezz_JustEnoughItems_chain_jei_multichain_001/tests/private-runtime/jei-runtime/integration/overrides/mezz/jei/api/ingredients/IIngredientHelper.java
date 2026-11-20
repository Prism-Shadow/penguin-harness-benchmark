package mezz.jei.api.ingredients;
public interface IIngredientHelper<T> {
    default String getErrorInfo(T t){
        return String.valueOf(t);
    }
    default java.util.Optional<net.minecraft.tags.TagKey<?>> getTagKeyEquivalent(java.util.List<T> values){
        return java.util.Optional.empty();
    }
    default T copyIngredient(T v){
        return v;
    }
    default IIngredientType<T> getIngredientType(){
        throw new AssertionError();
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
