package net.minecraft.world.inventory;
public class AbstractContainerMenu {
    public final java.util.List<Slot> slots=new java.util.ArrayList<>();
    public int broadcasts;
    public Slot getSlot(int id){
        return slots.get(id);
    }
    public void broadcastChanges(){
        broadcasts++;
    }
}
