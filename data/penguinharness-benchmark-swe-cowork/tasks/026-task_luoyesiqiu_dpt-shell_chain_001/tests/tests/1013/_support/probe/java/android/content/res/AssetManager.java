package android.content.res;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;

public class AssetManager {
    private byte[] appName = new byte[0];
    public void setAppName(String value) { appName = value.getBytes(java.nio.charset.StandardCharsets.UTF_8); }
    public InputStream open(String name) throws IOException {
        if (!"app_name".equals(name)) throw new IOException("unknown asset");
        return new ByteArrayInputStream(appName);
    }
}
