package com.luoyesiqiu.shell;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.res.AssetManager;

public final class ProbeContext extends Context {
    private final AssetManager assets = new AssetManager();
    private final ApplicationInfo info = new ApplicationInfo();
    @Override public AssetManager getAssets() { return assets; }
    @Override public ApplicationInfo getApplicationInfo() { return info; }
    public AssetManager mutableAssets() { return assets; }
}
