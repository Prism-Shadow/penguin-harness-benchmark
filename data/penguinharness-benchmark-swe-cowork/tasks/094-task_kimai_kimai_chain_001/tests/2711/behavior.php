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

$user = new App\Entity\User();
$user->setUsername('alice');
behavior_assert($user->getUsername() === 'alice' && $user->getDisplayName() === 'alice', 'user identity round-trip failed');
