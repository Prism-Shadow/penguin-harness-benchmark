package repair.spring;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.ImportResource;
import org.springframework.context.annotation.PropertySource;
import org.springframework.context.annotation.Scope;
import org.springframework.context.annotation.ScopedProxyMode;
import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;
import org.springframework.core.env.MapPropertySource;

public class ApplicationFixture implements AutoCloseable {
    private final ConfigurableApplicationContext context;
    private final ValueBean heldValue;
    private final LabelBean heldLabel;
    private final ClassBean heldClass;
    private final Settings heldSettings;

    public ApplicationFixture(boolean boot, String directory) {
        Path root = Paths.get(directory);
        Map<String, Object> locations = new HashMap<>();
        locations.put("fixture.properties", root.resolve("application.properties").toUri().toString());
        locations.put("fixture.xml", root.resolve("context.xml").toUri().toString());
        if (boot) {
            SpringApplication application = new SpringApplication(BootConfiguration.class);
            application.setWebApplicationType(WebApplicationType.NONE);
            application.setBannerMode(Banner.Mode.OFF);
            application.setRegisterShutdownHook(false);
            locations.put("spring.config.location", locations.get("fixture.properties"));
            application.setDefaultProperties(locations);
            context = application.run();
        } else {
            AnnotationConfigApplicationContext application = new AnnotationConfigApplicationContext();
            application.setClassLoader(getClass().getClassLoader());
            application.getEnvironment().getPropertySources().addFirst(new MapPropertySource("locations", locations));
            application.register(PlainConfiguration.class);
            application.refresh();
            context = application;
        }
        heldValue = context.getBean(ValueBean.class);
        heldLabel = context.getBean("label", LabelBean.class);
        heldClass = context.getBean("classBean", ClassBean.class);
        heldSettings = boot ? context.getBean(Settings.class) : null;
    }

    public String[] state() {
        return new String[] {heldValue.value(), context.getEnvironment().getProperty("fixture.value"),
                heldLabel.value(), heldClass.value(), heldSettings == null ? "plain" : heldSettings.getValue()};
    }

    public Class<?> changedClass() {
        return ClassBean.class;
    }

    @Override
    public void close() {
        context.close();
    }

    @Configuration
    @ImportResource("${fixture.xml}")
    public static class CommonConfiguration {
        @Bean
        public static PropertySourcesPlaceholderConfigurer placeholders() {
            return new PropertySourcesPlaceholderConfigurer();
        }

        @Bean
        @Scope(proxyMode = ScopedProxyMode.TARGET_CLASS)
        public ValueBean valueBean() {
            return new ValueBean();
        }
    }

    @Configuration
    @PropertySource("${fixture.properties}")
    public static class PlainConfiguration extends CommonConfiguration {}

    @Configuration
    @EnableConfigurationProperties
    public static class BootConfiguration extends CommonConfiguration {
        @Bean
        @Scope(proxyMode = ScopedProxyMode.TARGET_CLASS)
        public Settings settings() {
            return new Settings();
        }
    }

    public static class ValueBean {
        @Value("${fixture.value}")
        private String value;

        public String value() {
            return value;
        }
    }

    public static class LabelBean {
        private String value;

        public void setValue(String value) {
            this.value = value;
        }

        public String value() {
            return value;
        }
    }

    public static class ClassBean {
        private String value;

        public ClassBean() {
            value = "class-original";
        }

        public String value() {
            return value;
        }
    }

    @ConfigurationProperties(prefix = "fixture")
    public static class Settings {
        private String value;

        public void setValue(String value) {
            this.value = value;
        }

        public String getValue() {
            return value;
        }
    }
}
