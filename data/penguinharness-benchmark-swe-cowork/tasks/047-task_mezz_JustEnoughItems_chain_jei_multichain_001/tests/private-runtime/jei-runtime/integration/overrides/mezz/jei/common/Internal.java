package mezz.jei.common;
public class Internal {
    public static mezz.jei.api.runtime.IIngredientManager manager;
    public static int visibilityChecks;
    public static Runtime getJeiRuntime(){
        return new Runtime();
    }
    public static Configs getJeiClientConfigs(){
        return new Configs();
    }
    public static mezz.jei.common.gui.textures.Textures getTextures(){
        return new mezz.jei.common.gui.textures.Textures();
    }
    public static Keys getKeyMappings(){
        return new Keys();
    }
    public static class Keys{
        public Object getPauseRecipeCycling(){
            return null;
        }
    }
    public static class Configs{
        public mezz.jei.common.config.IClientConfig getClientConfig(){
            return new mezz.jei.common.config.IClientConfig(){
            }
            ;
        }
    }
    public static class Runtime{
        public Helpers getJeiHelpers(){
            return new Helpers();
        }
        public mezz.jei.api.runtime.IIngredientManager getIngredientManager(){
            return manager;
        }
    }
    public static class Helpers{
        public mezz.jei.api.runtime.IIngredientVisibility getIngredientVisibility(){
            return t->{
                visibilityChecks++;
                return true;
            }
            ;
        }
        public mezz.jei.api.helpers.IGuiHelper getGuiHelper(){
            throw new AssertionError();
        }
    }
}
