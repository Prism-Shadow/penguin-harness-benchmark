"""Headless game/UI boundaries; never substitutes scheduler or config logic."""


def sources():
    result = {
        'net.minecraft.resources.ResourceLocation': '''
public record ResourceLocation(String namespace, String path) {
 public static ResourceLocation fromNamespaceAndPath(String namespace, String path) { return new ResourceLocation(namespace,path); }
 public static ResourceLocation withDefaultNamespace(String path) { return fromNamespaceAndPath("minecraft",path); }
 public static ResourceLocation parse(String text) { String[] parts=text.split(":",2); return parts.length==2?fromNamespaceAndPath(parts[0],parts[1]):withDefaultNamespace(text); }
 public String getNamespace() { return namespace; }
 public String getPath() { return path; }
 public String toString() { return namespace+":"+path; }
}''',
        'net.minecraft.network.chat.Component': '''
public class Component {
 private final String text;
 public Component(String text) { this.text=text; }
 public static Component literal(String text) { return new Component(text); }
 public static Component translatable(String text,Object... args) { return new Component(text); }
 public static Component empty() { return literal(""); }
 public Component copy() { return new Component(text); }
 public Component append(Component other) { return literal(text+other.text); }
 public Component append(String other) { return literal(text+other); }
 public Component withStyle(net.minecraft.ChatFormatting... styles) { return this; }
 public String getString() { return text; }
}''',
        'net.minecraft.ChatFormatting': 'public enum ChatFormatting { WHITE,GRAY,GREEN,YELLOW,GOLD,RED }',
        'net.minecraft.locale.Language': '''public class Language {
 public static Language getInstance() { return new Language(); }
 public boolean has(String key) { return false; }
 public String getOrDefault(String key) { return key; }
}''',
        'net.minecraft.client.gui.screens.Screen': 'public class Screen {}',
        'net.minecraft.CrashReport': '''public record CrashReport(String message, Throwable cause) {
 public static CrashReport forThrowable(Throwable cause,String message) { return new CrashReport(message,cause); }
 public CrashReportCategory addCategory(String name,int level) { return new CrashReportCategory(); }
}''',
        'net.minecraft.client.Minecraft': '''public class Minecraft {
 private static final Minecraft INSTANCE=new Minecraft();
 public final java.io.File gameDirectory=new java.io.File(".");
 public Object level;
 public boolean smartCull=true;
 public final Renderer levelRenderer=new Renderer(), levelExtractor=new Renderer();
 public final Options options=new Options();
 public static Minecraft getInstance() { return INSTANCE; }
 public static void crash(Object context,java.io.File directory,net.minecraft.CrashReport report) { throw new IllegalStateException(report.message(),report.cause()); }
 public void updateMaxMipLevel(int value) {}
 public void delayTextureReload() {}
 public Window getWindow() { return new Window(); }
 public net.minecraft.client.renderer.blockentity.BlockEntityRenderDispatcher getBlockEntityRenderDispatcher() { return new net.minecraft.client.renderer.blockentity.BlockEntityRenderDispatcher(); }
 public static class Renderer { public void clearVisibleSections() {} public void needsUpdate() {} public void allChanged() {} }
 public static class Options { public java.util.function.Supplier<Integer> mipmapLevels() { return () -> 0; } }
 public static class Window { public void changeFullscreenVideoMode() {} }
}''',
        'net.minecraft.util.Mth': '''public class Mth {
 public static final float EPSILON=1.0e-5f;
 public static boolean equal(float first,float second) { return Math.abs(first-second)<EPSILON; }
 public static int clamp(int value,int min,int max) { return Math.max(min,Math.min(max,value)); }
 public static float clamp(float value,float min,float max) { return Math.max(min,Math.min(max,value)); }
 public static double clamp(double value,double min,double max) { return Math.max(min,Math.min(max,value)); }
 public static float square(float value) { return value*value; }
 public static int floor(double value) { return (int)Math.floor(value); }
 public static int ceil(float value) { return (int)Math.ceil(value); }
}''',
        'org.apache.commons.lang3.Validate': '''public class Validate {
 public static <T> T notNull(T value,String message,Object... args) { if(value==null) throw new NullPointerException(String.format(message,args)); return value; }
 public static void isTrue(boolean value,String message,Object... args) { if(!value) throw new IllegalArgumentException(String.format(message,args)); }
 public static String notBlank(String value,String message,Object... args) { notNull(value,message,args); isTrue(!value.isBlank(),message,args); return value; }
 public static String notEmpty(String value,String message,Object... args) { notNull(value,message,args); isTrue(!value.isEmpty(),message,args); return value; }
 public static <T extends java.util.Collection<?>> T notEmpty(T value,String message,Object... args) { notNull(value,message,args); isTrue(!value.isEmpty(),message,args); return value; }
}''',
        'com.google.common.collect.ImmutableList': '''public final class ImmutableList<T> extends java.util.AbstractList<T> {
 private final java.util.List<T> values;
 private ImmutableList(java.util.Collection<? extends T> values) { this.values=java.util.List.copyOf(values); }
 public static <T> ImmutableList<T> copyOf(java.util.Collection<? extends T> values) { return new ImmutableList<>(values); }
 @SafeVarargs public static <T> ImmutableList<T> of(T... values) { return new ImmutableList<>(java.util.List.of(values)); }
 public T get(int index) { return values.get(index); }
 public int size() { return values.size(); }
}''',
        'net.caffeinemc.mods.sodium.client.SodiumClientMod': '''public class SodiumClientMod {
 public static org.apache.logging.log4j.Logger logger() { return new org.apache.logging.log4j.Logger(); }
 public static Options options() { return new Options(); }
 public static class Options { public final Performance performance=new Performance(); }
 public static class Performance {
  public int chunkBuilderThreads=1;
  public boolean useFogOcclusion=true;
  public net.caffeinemc.mods.sodium.client.render.chunk.DeferMode chunkBuildDeferMode=net.caffeinemc.mods.sodium.client.render.chunk.DeferMode.ALWAYS;
  public net.caffeinemc.mods.sodium.client.render.chunk.translucent_sorting.QuadSplittingMode quadSplittingMode=net.caffeinemc.mods.sodium.client.render.chunk.translucent_sorting.QuadSplittingMode.SAFE;
 }
}''',
        'org.apache.logging.log4j.Logger': '''public class Logger {
 public void info(String text,Object... args) {}
 public void warn(String text,Object... args) {}
 public void error(String text,Object... args) {}
}''',
        'org.apache.logging.log4j.LogManager': '''public class LogManager {
 public static Logger getLogger(String name) { return new Logger(); }
}''',
        'net.caffeinemc.mods.sodium.client.console.Console': '''public class Console {
 public static Console instance() { return new Console(); }
 public void logMessage(net.caffeinemc.mods.sodium.client.console.message.MessageLevel level,String text,boolean translate,double seconds) {}
}''',
        'net.caffeinemc.mods.sodium.client.gui.options.control.Control': 'public interface Control {}',
        'org.jetbrains.annotations.ApiStatus': 'public class ApiStatus { public @interface Experimental {} public @interface Internal {} public @interface AvailableSince { String value(); } }',
    }
    for name in ('TickBoxControl', 'CyclingControl', 'SliderControl', 'ExternalButtonControl'):
        result['net.caffeinemc.mods.sodium.client.gui.options.control.' + name] = (
            'public class ' + name + ('<T>' if name == 'CyclingControl' else '') + ' implements Control { public ' + name + '(Object... args) {} }')
    for name in ('org.jspecify.annotations.NonNull', 'org.jspecify.annotations.Nullable',
                 'org.jetbrains.annotations.NotNull', 'org.jetbrains.annotations.Nullable'):
        result[name] = '@java.lang.annotation.Target({java.lang.annotation.ElementType.TYPE_USE,java.lang.annotation.ElementType.PARAMETER,java.lang.annotation.ElementType.METHOD,java.lang.annotation.ElementType.FIELD}) public @interface ' + name.rsplit('.', 1)[1] + ' {}'
    from integration_render_boundaries import render_sources
    result.update(render_sources())
    from integration_mesh_io import mesh_sources
    result.update(mesh_sources())
    return {name.replace('.', '/') + '.java': 'package ' + name.rsplit('.', 1)[0] + ';\n' + body + '\n'
            for name, body in result.items()}
