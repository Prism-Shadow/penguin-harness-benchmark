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

$team = new App\Entity\Team();
$user = new App\Entity\User();
$team->addUser($user);
behavior_assert(count($team->getUsers()) === 1 && $team->getUsers()[0] === $user, 'team membership round-trip failed');
