<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';
(new Symfony\Component\Dotenv\Dotenv(false))->loadEnv($repo . '/.env');
$kernel = new App\Kernel('test', true);
$kernel->boot();
$container = $kernel->getContainer();
$registry = $container->get('doctrine');
$entityManager = $registry->getManager();
