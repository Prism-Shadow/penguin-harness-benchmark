package mezz.jei.gui.input;
public class UserInput {
    public static java.util.Optional<UserInput> fromVanilla(net.minecraft.client.input.MouseButtonEvent e,boolean b,InputType t){
        return java.util.Optional.empty();
    }
    public static UserInput fromVanilla(net.minecraft.client.input.KeyEvent e,InputType t){
        return new UserInput();
    }
    public double getMouseX(){
        return 0;
    }
    public double getMouseY(){
        return 0;
    }
    public boolean is(Object key){
        return false;
    }
    public boolean isSimulate(){
        return false;
    }
}
