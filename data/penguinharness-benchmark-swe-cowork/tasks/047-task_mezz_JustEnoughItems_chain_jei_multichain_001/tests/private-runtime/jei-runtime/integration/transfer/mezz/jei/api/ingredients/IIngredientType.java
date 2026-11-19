package mezz.jei.api.ingredients;
public interface IIngredientType<T> {
    Class<? extends T> getIngredientClass();
    default T getCastIngredient(Object o){
        return getIngredientClass().isInstance(o)?(T)o:null;
    }
    default String getUid(){
        return getIngredientClass().getName();
    }
}
