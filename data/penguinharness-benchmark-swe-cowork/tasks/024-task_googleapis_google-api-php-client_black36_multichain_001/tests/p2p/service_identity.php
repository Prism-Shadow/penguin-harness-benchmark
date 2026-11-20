<?php
$repo = getenv('REPO_DIR') ?: '/workspace';
require_once $repo . '/vendor/autoload.php';
if (is_file($repo . '/src/aliases.php')) { require_once $repo . '/src/aliases.php'; }
$client = new Google_Client(['application_name' => 'compat-probe']);
$service = new Google_Service($client);
if ($service->getClient() !== $client) { exit(1); }
