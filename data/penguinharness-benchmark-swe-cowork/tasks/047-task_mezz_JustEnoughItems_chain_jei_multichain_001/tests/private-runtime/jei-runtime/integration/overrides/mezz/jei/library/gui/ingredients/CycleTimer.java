package mezz.jei.library.gui.ingredients;
public class CycleTimer implements ICycler {
    public static int index;
    public static CycleTimer create(int offset){
        return new CycleTimer();
    }
    public <T> java.util.Optional<T> getCycled(java.util.List<T> values){
        return values.isEmpty()?java.util.Optional.empty():java.util.Optional.ofNullable(values.get(index%values.size()));
    }
}
