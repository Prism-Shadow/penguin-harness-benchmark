package android.content;

import android.content.pm.ApplicationInfo;
import android.content.res.AssetManager;

public class Context {
    public AssetManager getAssets() { return new AssetManager(); }
    public ClassLoader getClassLoader() { return ClassLoader.getSystemClassLoader(); }
    public ApplicationInfo getApplicationInfo() { return new ApplicationInfo(); }
    public Context getApplicationContext() { return this; }
}
