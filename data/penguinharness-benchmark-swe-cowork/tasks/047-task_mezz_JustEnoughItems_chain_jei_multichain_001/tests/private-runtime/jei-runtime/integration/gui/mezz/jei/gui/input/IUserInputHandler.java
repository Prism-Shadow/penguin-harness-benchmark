package mezz.jei.gui.input;
public interface IUserInputHandler {
    default java.util.Optional<IUserInputHandler> handleUserInput(net.minecraft.client.gui.screens.Screen s,mezz.jei.api.gui.handlers.IGuiProperties p,UserInput i,mezz.jei.common.input.IInternalKeyMappings k){
        return java.util.Optional.empty();
    }
    default java.util.Optional<IUserInputHandler> handleMouseScrolled(double x,double y,double dx,double dy){
        return java.util.Optional.empty();
    }
}
