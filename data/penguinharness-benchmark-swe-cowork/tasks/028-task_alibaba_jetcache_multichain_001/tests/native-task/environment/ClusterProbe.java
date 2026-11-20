import com.alicp.jetcache.Cache;
import com.alicp.jetcache.CacheBuilder;
import com.alicp.jetcache.autoconfigure.AutoConfigureBeans;
import com.alicp.jetcache.autoconfigure.RedisAutoConfiguration;
import com.alicp.jetcache.autoconfigure.RedisLettuceAutoConfiguration;
import com.alicp.jetcache.external.ExternalCacheConfig;
import com.alicp.jetcache.redis.lettuce.RedisLettuceCacheConfig;
import io.lettuce.core.ReadFrom;
import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.cluster.ClusterClientOptions;
import io.lettuce.core.cluster.ClusterTopologyRefreshOptions;
import io.lettuce.core.cluster.RedisClusterClient;
import io.lettuce.core.cluster.api.StatefulRedisClusterConnection;
import io.lettuce.core.codec.RedisCodec;
import io.lettuce.core.masterreplica.MasterReplica;
import io.lettuce.core.masterreplica.StatefulRedisMasterReplicaConnection;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.apache.commons.pool2.impl.GenericObjectPoolConfig;
import org.mockito.MockedConstruction;
import org.mockito.MockedStatic;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.core.env.MapPropertySource;
import redis.clients.jedis.HostAndPort;
import redis.clients.jedis.JedisCluster;
import redis.clients.jedis.JedisPool;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockConstruction;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

public final class ClusterProbe {
    private static final String PROPERTY_PREFIX = "jetcache.remote.probe.";
    private static final String KEY_PREFIX = "cluster-probe:";

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static AnnotationConfigApplicationContext context(Map<String, Object> values, Class<?> configuration) {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
        context.getEnvironment().getPropertySources().addFirst(new MapPropertySource("behavior", values));
        context.register(AutoConfigureBeans.class, configuration);
        try {
            context.refresh();
            return context;
        } catch (RuntimeException failure) {
            context.close();
            throw failure;
        }
    }

    private static Map<String, Object> cacheProperties(String type) {
        Map<String, Object> values = new HashMap<>();
        values.put(PROPERTY_PREFIX + "type", type);
        values.put(PROPERTY_PREFIX + "keyPrefix", KEY_PREFIX);
        return values;
    }

    public static void singleUri() throws Exception {
        lettuce("cLuStEr", 1, null, null);
        lettuce("Cluster", 2, null, null);
        lettuce("MasterSlave", 1, null, null);
    }

    public static void topology() throws Exception {
        lettuce("Cluster", 1, null, null);
        lettuce("Cluster", 2, 17, false);
        lettuce("Cluster", 1, 29, true);
        lettuce("Cluster", 1, 0, true);
        lettuce("Cluster", 1, -1, false);
    }

    private static void lettuce(String mode, int seeds, Integer period, Boolean adaptive) throws Exception {
        RedisClusterClient clusterClient = mock(RedisClusterClient.class);
        RedisClient standaloneClient = mock(RedisClient.class);
        StatefulRedisClusterConnection<byte[], byte[]> clusterConnection = mock(StatefulRedisClusterConnection.class);
        StatefulRedisConnection<byte[], byte[]> standaloneConnection = mock(StatefulRedisConnection.class);
        StatefulRedisMasterReplicaConnection<byte[], byte[]> replicaConnection = mock(StatefulRedisMasterReplicaConnection.class);
        AtomicReference<ClusterClientOptions> configuredOptions = new AtomicReference<>();
        List<ClusterClientOptions> connectedOptions = new ArrayList<>();
        doAnswer(call -> {
            configuredOptions.set(call.getArgument(0));
            return null;
        }).when(clusterClient).setOptions(any(ClusterClientOptions.class));
        when(clusterClient.connect(any(RedisCodec.class))).thenAnswer(call -> {
            connectedOptions.add(configuredOptions.get());
            return clusterConnection;
        });
        when(standaloneClient.connect(any(RedisCodec.class))).thenReturn(standaloneConnection);
        AtomicInteger clusterCreates = new AtomicInteger();
        AtomicInteger standaloneCreates = new AtomicInteger();
        List<RedisURI> configuredSeeds = new ArrayList<>();
        try (MockedStatic<RedisClusterClient> clusterFactory = mockStatic(RedisClusterClient.class, invocation -> {
                 if (invocation.getMethod().getName().equals("create")) {
                     clusterCreates.incrementAndGet();
                     for (Object argument : invocation.getArguments()) {
                         if (argument instanceof Iterable) {
                             for (Object uri : (Iterable<?>) argument) {
                                 configuredSeeds.add((RedisURI) uri);
                             }
                         } else if (argument instanceof RedisURI[]) {
                             configuredSeeds.addAll(Arrays.asList((RedisURI[]) argument));
                         } else if (argument instanceof RedisURI) {
                             configuredSeeds.add((RedisURI) argument);
                         }
                     }
                     return clusterClient;
                 }
                 throw new AssertionError("unexpected cluster factory call: " + invocation.getMethod());
             });
             MockedStatic<RedisClient> standaloneFactory = mockStatic(RedisClient.class, invocation -> {
                 standaloneCreates.incrementAndGet();
                 return standaloneClient;
             });
             MockedStatic<MasterReplica> replicaFactory = mockStatic(MasterReplica.class, invocation -> replicaConnection)) {
            Map<String, Object> values = cacheProperties("redis.lettuce");
            String prefix = PROPERTY_PREFIX;
            values.put(prefix + "mode", mode);
            values.put(prefix + "uri.1", "redis://127.0.0.1:16379");
            if (seeds == 2) {
                values.put(prefix + "uri.2", "redis://127.0.0.1:16380");
            }
            values.put(prefix + "readFrom", "replicaPreferred");
            values.put(prefix + "asyncResultTimeoutInMillis", "321");
            if (period != null) {
                values.put(prefix + "enablePeriodicRefresh", period.toString());
            }
            if (adaptive != null) {
                values.put(prefix + "enableAllAdaptiveRefreshTriggers", adaptive.toString());
            }
            try (AnnotationConfigApplicationContext context = context(values, RedisLettuceAutoConfiguration.class)) {
                CacheBuilder builder = context.getBean(AutoConfigureBeans.class).getRemoteCacheBuilders().get("probe");
                require(builder != null, "public auto-configuration did not register the builder");
                try (Cache cache = builder.buildCache()) {
                    RedisLettuceCacheConfig config = (RedisLettuceCacheConfig) cache.config();
                    require(KEY_PREFIX.equals(config.getKeyPrefix()), "Lettuce lost the configured key prefix");
                    require(config.getAsyncResultTimeoutInMillis() == 321,
                            "Lettuce lost the configured async result timeout");
                    if (!mode.equalsIgnoreCase("Cluster")) {
                        require(clusterCreates.get() == 0 && standaloneCreates.get() > 0,
                                "standalone mode selected cluster factory");
                        require(cache.unwrap(RedisClient.class) == standaloneClient, "standalone client was not used");
                        return;
                    }
                    require(clusterCreates.get() > 0 && standaloneCreates.get() == 0,
                            "explicit cluster mode did not select the cluster factory");
                    require(cache.unwrap(RedisClusterClient.class) == clusterClient,
                            "created cluster client was not wired to the cache");
                    require(configuredSeeds.size() == seeds, "cluster factory lost URI seeds");
                    Set<Integer> ports = new java.util.HashSet<>();
                    for (RedisURI uri : configuredSeeds) {
                        require("127.0.0.1".equals(uri.getHost()), "cluster seed host changed");
                        ports.add(uri.getPort());
                    }
                    require(ports.equals(seeds == 1 ? Set.of(16379) : Set.of(16379, 16380)),
                            "cluster seed ports changed");
                    verify(clusterConnection, atLeastOnce()).setReadFrom(ReadFrom.REPLICA_PREFERRED);
                    require(!connectedOptions.isEmpty(), "cluster connection was not opened");
                    for (ClusterClientOptions options : connectedOptions) {
                        require(options != null, "cluster options were not applied before connecting");
                        ClusterTopologyRefreshOptions topology = options.getTopologyRefreshOptions();
                        int seconds = period == null ? 60 : period;
                        require(topology.isPeriodicRefreshEnabled() == (seconds > 0), "periodic refresh enablement changed");
                        if (seconds > 0) {
                            require(topology.getRefreshPeriod().equals(Duration.ofSeconds(seconds)),
                                    "periodic refresh unit/value is not seconds");
                        }
                        boolean enabled = adaptive == null || adaptive;
                        require(topology.getAdaptiveRefreshTriggers().isEmpty() == !enabled,
                                "adaptive refresh enablement changed");
                        if (enabled) {
                            require(topology.getAdaptiveRefreshTriggers().containsAll(
                                    Arrays.asList(ClusterTopologyRefreshOptions.RefreshTrigger.values())),
                                    "not all adaptive triggers were enabled");
                        }
                    }
                }
            }
        }
    }

    public static void jedis() throws Exception {
        for (boolean cluster : Arrays.asList(true, false)) {
            List<List<?>> clusterArguments = new ArrayList<>();
            List<List<?>> poolArguments = new ArrayList<>();
            try (MockedConstruction<JedisCluster> clusters = mockConstruction(JedisCluster.class,
                         (client, construction) -> clusterArguments.add(new ArrayList<>(construction.arguments())));
                 MockedConstruction<JedisPool> pools = mockConstruction(JedisPool.class,
                         (client, construction) -> poolArguments.add(new ArrayList<>(construction.arguments())))) {
                Map<String, Object> values = cacheProperties("redis");
                String prefix = PROPERTY_PREFIX;
                values.put(prefix + "poolConfig.maxTotal", "7");
                values.put(prefix + "connectionTimeout", "123");
                values.put(prefix + "soTimeout", "456");
                if (cluster) {
                    values.put(prefix + "cluster.1", "127.0.0.1:16379");
                    values.put(prefix + "cluster.2", "127.0.0.1:16380");
                } else {
                    values.put(prefix + "host", "127.0.0.1");
                    values.put(prefix + "port", "16379");
                }
                try (AnnotationConfigApplicationContext context = context(values, RedisAutoConfiguration.class)) {
                    CacheBuilder builder = context.getBean(AutoConfigureBeans.class).getRemoteCacheBuilders().get("probe");
                    require(builder != null, "Jedis auto-configuration did not register builder");
                    if (cluster) {
                        require(clusters.constructed().size() == 1 && pools.constructed().isEmpty(),
                                "Jedis cluster configuration used the pool branch");
                        List<?> arguments = clusterArguments.get(0);
                        require(arguments.contains(Set.of(new HostAndPort("127.0.0.1", 16379),
                                        new HostAndPort("127.0.0.1", 16380))), "Jedis lost cluster seeds");
                        boolean timeouts = arguments.contains(123) && arguments.contains(456);
                        for (Object argument : arguments) {
                            if (argument != null) {
                                try {
                                    Class<?> clientConfig = Class.forName("redis.clients.jedis.JedisClientConfig");
                                    if (clientConfig.isInstance(argument)) {
                                        timeouts = Integer.valueOf(123).equals(clientConfig.getMethod("getConnectionTimeoutMillis").invoke(argument))
                                                && Integer.valueOf(456).equals(clientConfig.getMethod("getSocketTimeoutMillis").invoke(argument));
                                    }
                                } catch (ClassNotFoundException absentInOlderJedis) {
                                    timeouts = arguments.contains(123) && arguments.contains(456);
                                }
                            }
                        }
                        require(timeouts, "Jedis lost timeout options");
                        Object config = builder.getClass().getMethod("getConfig").invoke(builder);
                        require(config.getClass().getMethod("getJedis").invoke(config) == clusters.constructed().get(0),
                                "Jedis factory result was not wired into the production builder");
                    } else {
                        require(clusters.constructed().isEmpty() && pools.constructed().size() == 1,
                                "standalone Jedis configuration used the cluster branch");
                    }
                    List<?> arguments = cluster ? clusterArguments.get(0) : poolArguments.get(0);
                    require(arguments.stream().anyMatch(argument -> argument instanceof GenericObjectPoolConfig
                                    && ((GenericObjectPoolConfig) argument).getMaxTotal() == 7),
                            "Jedis lost the configured pool limit");
                    try (Cache cache = builder.buildCache()) {
                        ExternalCacheConfig config = (ExternalCacheConfig) cache.config();
                        require(KEY_PREFIX.equals(config.getKeyPrefix()), "Jedis lost the configured key prefix");
                    }
                }
            }
        }
    }
}
