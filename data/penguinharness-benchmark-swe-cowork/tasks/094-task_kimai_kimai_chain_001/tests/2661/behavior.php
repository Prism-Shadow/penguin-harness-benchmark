<?php
declare(strict_types=1);

$repo = getenv('REPO_DIR') ?: dirname(__DIR__, 2);
require $repo . '/vendor/autoload.php';

function behavior_assert(bool $condition, string $message): void
{
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$duration = new App\Utils\Duration();
behavior_assert(is_string($duration->format(3661)), 'duration formatter did not return text');
behavior_assert(App\Constants::DEFAULT_LOCALE === 'en', 'default locale contract changed');
