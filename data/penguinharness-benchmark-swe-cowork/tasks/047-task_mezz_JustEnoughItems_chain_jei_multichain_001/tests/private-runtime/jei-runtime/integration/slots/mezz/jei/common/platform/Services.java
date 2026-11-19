package mezz.jei.common.platform;
public class Services {
    public static final Platform PLATFORM=new Platform();
    public static class Platform {
        public IPlatformFluidHelperInternal<?> getFluidHelper(){
            throw new AssertionError();
        }
    }
}
