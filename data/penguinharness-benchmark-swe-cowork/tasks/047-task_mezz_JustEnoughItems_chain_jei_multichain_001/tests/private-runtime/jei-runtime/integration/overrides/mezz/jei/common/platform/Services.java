package mezz.jei.common.platform;
public class Services {
    public static final Platform PLATFORM=new Platform();
    public static class ModHelper {
        public boolean isInDev(){
            return false;
        }
    }
    public static class Platform {
        public ModHelper getModHelper(){
            return new ModHelper();
        }
        public IPlatformFluidHelperInternal<?> getFluidHelper(){
            throw new AssertionError();
        }
        public IPlatformRenderHelper getRenderHelper(){
            throw new AssertionError();
        }
        public IPlatformScreenHelper getScreenHelper(){
            throw new AssertionError();
        }
    }
}
