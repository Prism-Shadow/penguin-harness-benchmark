<?php
$repo = getenv('REPO_DIR') ?: '/workspace';
require_once $repo . '/vendor/autoload.php';
if (is_file($repo . '/src/aliases.php')) { require_once $repo . '/src/aliases.php'; }
$service = new Google_Service(['application_name' => 'compat-probe']);
if (!($service->getClient() instanceof Google_Client)) { exit(1); }
