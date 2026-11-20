package org.apache.logging.log4j;
public interface Logger {
    default void debug(String message, Object... args) {
    }
    default void warn(String message, Object... args) {
    }
    default void error(String message, Object... args) {
    }
    default void info(String message, Object... args) {
    }
}
