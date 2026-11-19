package net.minecraft.world.item;
public class ItemStack {
    public static final ItemStack EMPTY=new ItemStack("",0);
    public final String item;
    private int count;
    public ItemStack(String item,int count){
        this.item=item;
        this.count=count;
    }
    public ItemStack copy(){
        return new ItemStack(item,count);
    }
    public int getCount(){
        return count;
    }
    public void setCount(int n){
        count=n;
    }
    public void grow(int n){
        count+=n;
    }
    public boolean isEmpty(){
        return count<=0 || item.isEmpty();
    }
    public boolean isStackable(){
        return true;
    }
    public static boolean isSameItemSameComponents(ItemStack a,ItemStack b){
        return a.item.equals(b.item);
    }
    public String toString(){
        return item+":"+count;
    }
}
