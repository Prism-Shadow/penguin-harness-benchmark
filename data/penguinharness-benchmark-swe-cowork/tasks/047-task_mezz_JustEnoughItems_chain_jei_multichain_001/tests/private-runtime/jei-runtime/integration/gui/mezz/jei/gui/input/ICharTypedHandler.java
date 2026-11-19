package mezz.jei.gui.input;
public interface ICharTypedHandler {
    boolean hasKeyboardFocus();
    boolean onCharTyped(net.minecraft.client.input.CharacterEvent e);
}
