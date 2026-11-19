package dalvik.system;

public class PathClassLoader extends ClassLoader {
    public final String dexPath;
    public final String librarySearchPath;
    public PathClassLoader(String dexPath, String librarySearchPath, ClassLoader parent) {
        super(parent);
        this.dexPath = dexPath;
        this.librarySearchPath = librarySearchPath;
    }
    @Override protected Class<?> findClass(String name) throws ClassNotFoundException { throw new ClassNotFoundException(name); }
}
