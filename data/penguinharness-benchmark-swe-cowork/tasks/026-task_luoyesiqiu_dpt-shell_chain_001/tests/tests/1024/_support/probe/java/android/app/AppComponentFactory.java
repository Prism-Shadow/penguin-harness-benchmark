package android.app;

import android.content.ContentProvider;
import android.content.BroadcastReceiver;
import android.content.Intent;
import android.content.pm.ApplicationInfo;

public class AppComponentFactory {
    public Service instantiateService(ClassLoader cl, String name, Intent intent) throws ClassNotFoundException, IllegalAccessException, InstantiationException { return (Service) cl.loadClass(name).newInstance(); }
    public Application instantiateApplication(ClassLoader cl, String name) throws ClassNotFoundException, IllegalAccessException, InstantiationException { return (Application) cl.loadClass(name).newInstance(); }
    public Activity instantiateActivity(ClassLoader cl, String name, Intent intent) throws ClassNotFoundException, IllegalAccessException, InstantiationException { return (Activity) cl.loadClass(name).newInstance(); }
    public ContentProvider instantiateProvider(ClassLoader cl, String name) throws ClassNotFoundException, IllegalAccessException, InstantiationException { return (ContentProvider) cl.loadClass(name).newInstance(); }
    public BroadcastReceiver instantiateReceiver(ClassLoader cl, String name, Intent intent) throws ClassNotFoundException, IllegalAccessException, InstantiationException { return (BroadcastReceiver) cl.loadClass(name).newInstance(); }
    public ClassLoader instantiateClassLoader(ClassLoader cl, ApplicationInfo info) { return cl; }
}
