import com.alicp.jetcache.CacheManager;
import com.alicp.jetcache.CacheResult;
import com.alicp.jetcache.external.ExternalCacheBuilder;
import com.alicp.jetcache.support.BroadcastManager;
import com.alicp.jetcache.support.CacheMessage;

/** Public consumer example. The caller supplies a fully configured builder. */
public final class CacheBroadcastApiExample {
    public static CacheResult publish(ExternalCacheBuilder<?> builder,
                                      CacheManager registry, CacheMessage message) throws Exception {
        if (!builder.supportBroadcast()) {
            throw new IllegalArgumentException("adapter has no broadcast capability");
        }
        try (BroadcastManager broadcaster = builder.createBroadcastManager(registry)) {
            broadcaster.startSubscribe();
            return broadcaster.publish(message);
        }
    }
}
