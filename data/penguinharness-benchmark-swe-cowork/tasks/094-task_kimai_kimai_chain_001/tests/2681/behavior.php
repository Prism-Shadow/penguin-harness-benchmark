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

behavior_assert(is_a(App\Security\DoctrineUserProvider::class, Symfony\Component\Security\Core\User\UserProviderInterface::class, true), 'doctrine provider contract missing');
$reflection = new ReflectionClass(App\Ldap\LdapAuthenticationProvider::class);
behavior_assert($reflection->hasMethod('retrieveUser'), 'ldap provider retrieval contract missing');
