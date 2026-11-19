package mezz.jei.gui.filter;
public interface IFilterTextSource {
    String getFilterText();
    void setFilterText(String text);
    void addListener(java.util.function.BiConsumer<String,String> listener);
}
