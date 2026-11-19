package android.app;

import android.content.Context;

public class Application extends Context {
    private Context base;

    public void onCreate() {}

    protected void attachBaseContext(Context context) {
        base = context;
    }

    @Override
    public android.content.res.AssetManager getAssets() {
        return base == null ? super.getAssets() : base.getAssets();
    }

    @Override
    public ClassLoader getClassLoader() {
        return base == null ? super.getClassLoader() : base.getClassLoader();
    }

    @Override
    public android.content.pm.ApplicationInfo getApplicationInfo() {
        return base == null ? super.getApplicationInfo() : base.getApplicationInfo();
    }
}
