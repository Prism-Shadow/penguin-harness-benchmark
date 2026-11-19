package net.minecraft.world.inventory;
public class Slot {
    public final int index;
    public boolean place=true,pickup=true,fake=false;
    private net.minecraft.world.item.ItemStack item;
    public int removals,sets,inserts;
    public Slot(int index,String item,int count){
        this.index=index;
        this.item=new net.minecraft.world.item.ItemStack(item,count);
    }
    public net.minecraft.world.item.ItemStack getItem(){
        return item;
    }
    public boolean mayPlace(net.minecraft.world.item.ItemStack s){
        return place;
    }
    public boolean mayPickup(net.minecraft.world.entity.player.Player p){
        return pickup;
    }
    public boolean allowModification(net.minecraft.world.entity.player.Player p){
        return pickup&&place;
    }
    public boolean isFake(){
        return fake;
    }
    public int getMaxStackSize(net.minecraft.world.item.ItemStack s){
        return 64;
    }
    public net.minecraft.world.item.ItemStack safeTake(int amount,int limit,net.minecraft.world.entity.player.Player p){
        removals++;
        if(!allowModification(p))return net.minecraft.world.item.ItemStack.EMPTY;
        int n=Math.min(Math.min(amount,limit),item.getCount());
        var taken=item.copy();
        taken.setCount(n);
        item.setCount(item.getCount()-n);
        return taken;
    }
    public void set(net.minecraft.world.item.ItemStack s){
        sets++;
        item=s;
    }
    public net.minecraft.world.item.ItemStack safeInsert(net.minecraft.world.item.ItemStack s){
        return safeInsert(s,64);
    }
    public net.minecraft.world.item.ItemStack safeInsert(net.minecraft.world.item.ItemStack s,int limit){
        inserts++;
        var rest=s.copy();
        if(!mayPlace(s)||s.isEmpty())return rest;
        if(!item.isEmpty()&&!net.minecraft.world.item.ItemStack.isSameItemSameComponents(item,s))return rest;
        int n=Math.min(s.getCount(),Math.min(limit,64-(item.isEmpty()?0:item.getCount())));
        if(n>0){
            var next=s.copy();
            next.setCount((item.isEmpty()?0:item.getCount())+n);
            set(next);
            rest.setCount(s.getCount()-n);
        }
        return rest;
    }
}
