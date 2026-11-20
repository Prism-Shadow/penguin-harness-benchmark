import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;
import java.util.function.Supplier;
import org.mapdb.DBMaker;
import okhttp3.OkHttpClient;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.telegram.telegrambots.abilitybots.api.bot.BaseAbilityBot;
import org.telegram.telegrambots.abilitybots.api.db.MapDBContext;
import org.telegram.telegrambots.abilitybots.api.objects.Flag;
import org.telegram.telegrambots.abilitybots.api.objects.Reply;
import org.telegram.telegrambots.abilitybots.api.toggle.DefaultToggle;
import org.telegram.telegrambots.abilitybots.api.util.AbilityUtils;
import org.telegram.telegrambots.longpolling.BotSession;
import org.telegram.telegrambots.longpolling.TelegramBotsLongPollingApplication;
import org.telegram.telegrambots.longpolling.interfaces.LongPollingUpdateConsumer;
import org.telegram.telegrambots.longpolling.starter.AfterBotRegistration;
import org.telegram.telegrambots.longpolling.starter.SpringLongPollingBot;
import org.telegram.telegrambots.longpolling.starter.TelegramBotInitializer;
import org.telegram.telegrambots.longpolling.starter.TelegramBotStarterConfiguration;
import org.telegram.telegrambots.meta.TelegramUrl;
import org.telegram.telegrambots.meta.api.methods.updates.GetUpdates;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.generics.TelegramClient;

public final class IntegrationProbe {
    private IntegrationProbe() {
    }

    public static final class PurchaseBot extends BaseAbilityBot {
        final List<Long> buyers = new ArrayList<>();

        PurchaseBot(MapDBContext database) {
            super(org.mockito.Mockito.mock(TelegramClient.class), "probe_bot", database, new DefaultToggle());
        }

        @Override
        public long creatorId() {
            return 9999L;
        }

        public Reply purchaseReply() {
            return Reply.of((bot, update) -> buyers.add(AbilityUtils.getChatId(update)),
                    Flag.valueOf("HAS_PAID_MEDIA_PURCHASED"));
        }
    }

    public static void purchases() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        MapDBContext database = new MapDBContext(DBMaker.memoryDB().make());
        try {
            PurchaseBot bot = new PurchaseBot(database);
            bot.onRegister();
            for (long buyerId : new long[] {42L, 913L}) {
                Update update = mapper.readValue("{\"update_id\":7,\"purchased_paid_media\":{\"from\":{\"id\":"
                        + buyerId + ",\"first_name\":\"Buyer\",\"is_bot\":false},\"paid_media_payload\":\"receipt-"
                        + buyerId + "\"}}", Update.class);
                require(AbilityUtils.getUser(update).getId() == buyerId, "purchase origin user");
                require(AbilityUtils.getChatId(update) == buyerId, "purchase chat routing");
                bot.consume(update);
            }
            Update ordinary = mapper.readValue("{\"update_id\":8,\"message\":{\"message_id\":19,"
                    + "\"date\":1,\"chat\":{\"id\":-801,\"type\":\"group\"},"
                    + "\"from\":{\"id\":63,\"first_name\":\"Ordinary\",\"is_bot\":false}}}", Update.class);
            require(AbilityUtils.getUser(ordinary).getId() == 63L, "ordinary user regression");
            require(AbilityUtils.getChatId(ordinary) == -801L, "ordinary chat regression");
            require(!Flag.valueOf("HAS_PAID_MEDIA_PURCHASED").test(ordinary), "ordinary update is not a purchase");
            require(!Flag.valueOf("HAS_PAID_MEDIA_PURCHASED").test(new Update()), "empty update is not a purchase");
            bot.consume(ordinary);
            require(bot.buyers.equals(List.of(42L, 913L)), "consume must dispatch only purchases");
            require(bot.users().containsKey(913L), "consume must maintain the user database");
        } finally {
            database.close();
        }
    }

    public static final class StartupBot implements SpringLongPollingBot {
        private final String token;
        final CountDownLatch received;
        boolean registered;

        StartupBot(String token, CountDownLatch received) {
            this.token = token;
            this.received = received;
        }

        @Override
        public String getBotToken() {
            return token;
        }

        @Override
        public LongPollingUpdateConsumer getUpdatesConsumer() {
            return updates -> {
                if (updates.stream().anyMatch(update -> update.getUpdateId() == 812)) {
                    received.countDown();
                }
            };
        }

        @AfterBotRegistration
        public void registered(BotSession session) {
            require(session != null, "registration hook session");
            registered = true;
        }
    }

    public static final class RegistrationBoundary extends TelegramBotsLongPollingApplication {
        final List<TelegramUrl> endpoints = new ArrayList<>();

        @Override
        public BotSession registerBot(String token, Supplier<TelegramUrl> endpoint,
                                      Function<Integer, GetUpdates> requests, LongPollingUpdateConsumer consumer) {
            endpoints.add(endpoint.get());
            return org.mockito.Mockito.mock(BotSession.class);
        }
    }

    public static void spring() throws Exception {
        RegistrationBoundary boundary = new RegistrationBoundary();
        StartupBot defaultBot = new StartupBot("default-token", new CountDownLatch(1));
        try (AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext()) {
            context.registerBean(TelegramBotsLongPollingApplication.class, () -> boundary);
            context.registerBean(SpringLongPollingBot.class, () -> defaultBot);
            context.register(TelegramBotStarterConfiguration.class);
            context.refresh();
            require(context.getBean(TelegramBotInitializer.class) != null, "default initializer lifecycle");
            require(boundary.endpoints.equals(List.of(TelegramUrl.DEFAULT_URL)), "default registration endpoint");
            require(defaultBot.registered, "default registration hook");
        }
        try (AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext()) {
            context.register(TelegramBotStarterConfiguration.class);
            context.refresh();
            require(context.getBean(TelegramBotInitializer.class) != null, "empty bot list");
        }
        for (String token : List.of("first-token", "second-token")) {
            HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            List<String> paths = java.util.Collections.synchronizedList(new ArrayList<>());
            server.createContext("/", exchange -> {
                String path = exchange.getRequestURI().getPath();
                paths.add(path);
                exchange.getRequestBody().readAllBytes();
                String result = ContractProbe.endpoint(path, token, "getUpdates") ? "[{\"update_id\":812}]" : "true";
                byte[] response = ("{\"ok\":true,\"result\":" + result + "}").getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(200, response.length);
                exchange.getResponseBody().write(response);
                exchange.close();
            });
            server.start();
            TelegramUrl custom = new TelegramUrl("http", "127.0.0.1", server.getAddress().getPort(), false);
            CountDownLatch received = new CountDownLatch(1);
            StartupBot bot = new StartupBot(token, received);
            ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor();
            OkHttpClient http = new OkHttpClient.Builder().callTimeout(3, TimeUnit.SECONDS).build();
            try (AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext()) {
                context.registerBean(TelegramBotsLongPollingApplication.class,
                        () -> new TelegramBotsLongPollingApplication(ObjectMapper::new, () -> http, () -> executor));
                context.registerBean(TelegramUrl.class, () -> custom);
                context.registerBean(SpringLongPollingBot.class, () -> bot);
                context.register(TelegramBotStarterConfiguration.class);
                context.refresh();
                require(received.await(8, TimeUnit.SECONDS), "custom endpoint must deliver a real update");
                require(paths.stream().anyMatch(path -> ContractProbe.endpoint(path, token, "deleteWebhook")), "startup custom endpoint");
                require(paths.stream().anyMatch(path -> ContractProbe.endpoint(path, token, "getUpdates")), "polling custom endpoint");
                require(bot.registered, "custom registration hook");
            } finally {
                executor.shutdownNow();
                http.dispatcher().executorService().shutdownNow();
                http.connectionPool().evictAll();
                server.stop(0);
                require(executor.awaitTermination(5, TimeUnit.SECONDS), "fixture executor terminated");
            }
            try (RegistrationBoundary manual = new RegistrationBoundary()) {
                TelegramBotInitializer initializer = TelegramBotInitializer.class.getConstructor(
                        TelegramBotsLongPollingApplication.class, List.class, TelegramUrl.class)
                        .newInstance(manual, List.of(new StartupBot(token, new CountDownLatch(1))), custom);
                initializer.afterPropertiesSet();
                require(manual.endpoints.size() == 1 && manual.endpoints.get(0) == custom, "manual endpoint preserved");
                new TelegramBotInitializer(manual, List.of()).afterPropertiesSet();
            }
        }
    }

    private static void require(boolean value, String message) {
        if (!value) {
            throw new AssertionError(message);
        }
    }
}
