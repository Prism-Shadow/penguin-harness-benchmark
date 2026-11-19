package mezz.jei.common;
public class Internal {
    public static mezz.jei.common.config.IClientConfig config;
    public static Configs getJeiClientConfigs(){
        return new Configs();
    }
    public static class Configs{
        public mezz.jei.common.config.IClientConfig getClientConfig(){
            return config;
        }
    }
    public static mezz.jei.common.gui.textures.Textures getTextures(){
        return new mezz.jei.common.gui.textures.Textures();
    }
}
