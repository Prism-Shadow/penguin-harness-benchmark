public final class RuntimePreflight {
    public static void main(String[] args) throws Exception {
        for (String name : new String[]{"redis.clients.jedis.Jedis", "io.lettuce.core.RedisClient",
                "org.redisson.api.RedissonClient", "org.springframework.context.annotation.AnnotationConfigApplicationContext",
                "org.mockito.Mockito", "net.bytebuddy.ClassFileVersion",
                "net.bytebuddy.agent.ByteBuddyAgent", "org.objenesis.Objenesis"}) {
            Class<?> loaded = Class.forName(name);
            System.out.println("runtime dependency: " + name + " from "
                    + loaded.getProtectionDomain().getCodeSource().getLocation());
        }
        if (args.length > 0 && Integer.parseInt(args[0].split("\\.")[0]) >= 4) {
            Class<?> unified = Class.forName("redis.clients.jedis.UnifiedJedis");
            System.out.println("UnifiedJedis from " + unified.getProtectionDomain().getCodeSource().getLocation());
        }
        // Exercise binary buffers and actual offline transports before any scoring node.
        io.netty.buffer.ByteBuf buffer = io.netty.buffer.Unpooled.buffer();
        try { buffer.writeLong(42L); if (buffer.readLong() != 42L) throw new IllegalStateException("Netty buffer corruption"); }
        finally { buffer.release(); }
        org.apache.commons.pool2.impl.GenericObjectPoolConfig<Object> pool =
                new org.apache.commons.pool2.impl.GenericObjectPoolConfig<>();
        pool.setMaxWait(java.time.Duration.ofMillis(1000));
        if (pool.getMaxWaitDuration().toMillis() != 1000) throw new IllegalStateException("pool Duration API");
        try (DeepBehaviorProbe.Redis redis = new DeepBehaviorProbe.Redis()) {
            io.lettuce.core.RedisClient client = io.lettuce.core.RedisClient.create(redis.uri());
            try (io.lettuce.core.api.StatefulRedisConnection<String,String> connection = client.connect()) {
                if (!"PONG".equals(connection.sync().ping())) throw new IllegalStateException("Lettuce preflight ping");
            } finally { client.shutdown(); }
            org.redisson.api.RedissonClient redisson = DeepBehaviorProbe.redissonClient(redis, true);
            try {
                redisson.getBucket("preflight").set("ready");
                if (!"ready".equals(redisson.getBucket("preflight").get())) throw new IllegalStateException("Redisson preflight round-trip");
            } finally { redisson.shutdown(); }
            org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory factory =
                    new org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory("127.0.0.1", redis.port);
            factory.afterPropertiesSet();
            try (org.springframework.data.redis.connection.RedisConnection connection = factory.getConnection()) {
                if (!"PONG".equals(connection.ping())) throw new IllegalStateException("Spring preflight ping");
            } finally { factory.destroy(); }
        }
        System.out.println("real Redis/Jedis/Lettuce/Redisson/Spring driver preflight passed");
        io.lettuce.core.RedisClient expected = org.mockito.Mockito.mock(io.lettuce.core.RedisClient.class);
        try (org.mockito.MockedStatic<io.lettuce.core.RedisClient> factory =
                     org.mockito.Mockito.mockStatic(io.lettuce.core.RedisClient.class)) {
            factory.when(() -> io.lettuce.core.RedisClient.create("redis://127.0.0.1:1"))
                    .thenReturn(expected);
            if (io.lettuce.core.RedisClient.create("redis://127.0.0.1:1") != expected) {
                throw new IllegalStateException("static client-factory interception failed");
            }
            System.out.println("static client-factory instrumentation available");
        }
        try (org.mockito.MockedConstruction<redis.clients.jedis.JedisPool> pools =
                     org.mockito.Mockito.mockConstruction(redis.clients.jedis.JedisPool.class)) {
            redis.clients.jedis.JedisPool interceptedPool = new redis.clients.jedis.JedisPool();
            interceptedPool.close();
            if (pools.constructed().size() != 1 || pools.constructed().get(0) != interceptedPool) {
                throw new IllegalStateException("client-constructor interception failed");
            }
            org.mockito.Mockito.verify(interceptedPool).close();
            System.out.println("client-constructor instrumentation available");
        }
    }
}
