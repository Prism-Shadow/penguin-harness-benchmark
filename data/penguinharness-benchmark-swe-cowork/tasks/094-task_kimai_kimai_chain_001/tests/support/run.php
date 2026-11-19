<?php
declare(strict_types=1);

register_shutdown_function(function (): void {
    $error = error_get_last();
    if ($error !== null && in_array($error['type'], [E_PARSE, E_COMPILE_ERROR], true)) {
        $repository = realpath(getenv('REPO_DIR_OVERRIDE') ?: getenv('REPO_DIR'));
        exit($repository !== false && strpos($error['file'], $repository . '/') === 0 ? 3 : 2);
    }
});

try {
    require $argv[1];
} catch (ParseError $error) {
    fwrite(STDERR, 'production compile error: ' . $error->getMessage() . PHP_EOL);
    $repository = realpath(getenv('REPO_DIR_OVERRIDE') ?: getenv('REPO_DIR'));
    exit($repository !== false && strpos($error->getFile(), $repository . '/') === 0 ? 3 : 2);
} catch (Throwable $error) {
    fwrite(STDERR, get_class($error) . ': ' . $error->getMessage() . PHP_EOL . $error->getTraceAsString() . PHP_EOL);
    exit(1);
}
