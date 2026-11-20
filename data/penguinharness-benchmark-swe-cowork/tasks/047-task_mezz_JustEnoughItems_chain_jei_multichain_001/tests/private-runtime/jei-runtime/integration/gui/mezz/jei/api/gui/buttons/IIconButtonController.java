package mezz.jei.api.gui.buttons;
public interface IIconButtonController {
    boolean onPress(mezz.jei.api.gui.inputs.IJeiUserInput i);
    void initState(IButtonState s);
    void updateState(IButtonState s);
}
