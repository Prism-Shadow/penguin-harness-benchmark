package mezz.jei.library.ingredients;
import java.util.*;
import java.util.stream.*;
import mezz.jei.api.ingredients.*;
import mezz.jei.api.recipe.*;
import mezz.jei.common.ingredients.TypedIngredient;
import mezz.jei.library.load.registration.SlotDisplayInterpreterRegistration;
import net.minecraft.util.context.ContextMap;
import net.minecraft.world.item.crafting.display.*;
public class Fixture implements IIngredientManagerInternal {
    public static final IIngredientType<String> TYPE=()->String.class;
    public final SlotDisplayInterpreterRegistration registration=new SlotDisplayInterpreterRegistration();
    public boolean subtypes=true;
    public int expansions;
    public List<String> grouped=List.of("o:red","o:blue");
    public final IIngredientHelper<String> helper=new IIngredientHelper<>() {
        public boolean isValidIngredient(String s){
            return !s.startsWith("invalid");
        }
        public boolean hasSubtypes(String s){
            return subtypes;
        }
        public Object getGroupingUid(ITypedIngredient<String> t){
            return t.getIngredient().split(":")[0];
        }
    }
    ;
    public static class Display implements SlotDisplay {
        public static final Type<Display> TYPE=new Type<>();
        public final List<String> raw;
        public final java.util.function.Consumer<ISlotDisplayInterpretationBuilder<String>> interpretation;
        public Display(List<String> raw,java.util.function.Consumer<ISlotDisplayInterpretationBuilder<String>> interpretation){
            this.raw=raw;
            this.interpretation=interpretation;
        }
        public Type<Display> type(){
            return TYPE;
        }
        public <T> Stream<T> resolve(ContextMap c,DisplayContentsFactory<T> f){
            return raw.stream().map(v->(T)v);
        }
    }
    public Fixture(){
        registration.register(Display.TYPE,TYPE,(d,c,b)->d.interpretation.accept(b));
    }
    public Display leaf(String... values){
        return new Display(List.of(values),b->{
        }
        );
    }
    public <T> IIngredientHelper<T> getIngredientHelper(IIngredientType<T> type){
        if(type!=TYPE)throw new AssertionError();
        return (IIngredientHelper<T>)helper;
    }
    public Collection<IIngredientType<?>> getRegisteredIngredientTypes(){
        return List.of(TYPE);
    }
    public <T> IIngredientType<T> getIngredientType(T value){
        return (IIngredientType<T>)TYPE;
    }
    public <T> List<ITypedIngredient<T>> getGroupedIngredients(ITypedIngredient<T> t){
        expansions++;
        if(!helper.getGroupingUid((ITypedIngredient<String>)t).equals("o"))return List.of();
        return grouped.stream().map(v->(ITypedIngredient<T>)typed(v)).toList();
    }
    public Stream<SlotIngredient<?>> resolveSlotDisplay(ContextMap c,RecipeIngredientRole r,SlotDisplay d){
        return SlotDisplayIngredientResolver.resolve(this,registration.createRegistry(),c,r,d);
    }
    public <T> Stream<SlotIngredient<T>> resolveSlotDisplay(IIngredientType<T> t,ContextMap c,RecipeIngredientRole r,SlotDisplay d){
        return SlotDisplayIngredientResolver.resolve(this,registration.createRegistry(),t,c,r,d);
    }
    public List<SlotIngredient<String>> resolve(Display d,RecipeIngredientRole r){
        return resolveSlotDisplay(TYPE,ContextMap.EMPTY,r,d).toList();
    }
    public static ITypedIngredient<String> typed(String v){
        return TypedIngredient.createUnvalidated(TYPE,v);
    }
    public static List<String> values(List<? extends SlotIngredient<?>> list){
        return list.stream().map(v->v.typedIngredient().getIngredient().toString()).toList();
    }
    public static void check(boolean b,String message){
        if(!b)throw new AssertionError(message);
    }
}
