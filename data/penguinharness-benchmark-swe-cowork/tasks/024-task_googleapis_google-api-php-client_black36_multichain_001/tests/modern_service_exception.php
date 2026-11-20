<?php
declare(strict_types=1);

$repo = getenv('REPO_DIR') ?: '/workspace';
require_once $repo . '/vendor/autoload.php';
require_once __DIR__ . '/service_exception_contract.php';
verify_service_exception_chain('Google\\Service\\Exception');
