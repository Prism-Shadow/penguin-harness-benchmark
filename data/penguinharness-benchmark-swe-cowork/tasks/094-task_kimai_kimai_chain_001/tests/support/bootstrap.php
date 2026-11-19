<?php
declare(strict_types=1);

$repo = getenv('REPO_DIR_OVERRIDE') ?: (getenv('REPO_DIR') ?: dirname(__DIR__, 2) . '/environment/base');
require_once $repo . '/vendor/autoload.php';

if (!function_exists('behavior_assert')) {
    function behavior_assert(bool $condition, string $message): void
    {
        if (!$condition) {
            throw new RuntimeException($message);
        }
    }
}
