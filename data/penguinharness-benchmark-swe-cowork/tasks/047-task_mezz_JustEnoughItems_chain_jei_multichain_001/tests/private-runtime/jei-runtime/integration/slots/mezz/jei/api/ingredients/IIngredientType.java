package mezz.jei.api.ingredients;
public interface IIngredientType<T> {
    Class<? extends T> getIngredientClass();
    default T getCastIngredient(Object o){
        return getIngredientClass().isInstance(o)?(T)o:null;
    }
    default java.util.Optional<T> castIngredient(Object o){
        return java.util.Optional.ofNullable(getCastIngredient(o));
    }
    default String getUid(){
        return getIngredientClass().getName();
    }
}
