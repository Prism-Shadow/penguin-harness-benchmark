package com.luoyesiqiu.shell;

import android.content.Context;
import java.util.ArrayList;
import java.util.List;

public final class JniBridge {
    public static final List<String> calls = new ArrayList<>();
    public static void reset() { calls.clear(); }
    public static void craoc(String name) { calls.add("craoc:" + name); }
    public static void craa(Context context, String name) { calls.add("craa:" + name); }
    public static void ia(Context context) { calls.add("ia1"); }
    public static void ia(Context context, ClassLoader loader) { calls.add("ia2"); }
    public static String rcf() { calls.add("rcf0"); return ""; }
    public static String rcf(ClassLoader loader) { calls.add("rcf1"); return ""; }
    public static void mde(ClassLoader oldLoader, ClassLoader newLoader) { calls.add("mde"); }
    public static void rde(ClassLoader loader, String name) { calls.add("rde:" + name); }
    public static String gap() { calls.add("gap"); return ""; }
    public static String gdp() { calls.add("gdp"); return ""; }
    public static void ra(String name) { calls.add("ra:" + name); }
    public static String rapn() { calls.add("rapn0"); return ""; }
    public static String rapn(ClassLoader loader) { calls.add("rapn1"); return ""; }
    public static void loadShellLibs(String workspace, String apk) { calls.add("loadShellLibs"); }
}
