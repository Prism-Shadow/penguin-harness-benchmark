<?php
// Loading dependencies must use the actual package autoloader.
$repo = getenv('REPO_DIR') ?: '/workspace';
require_once $repo . '/vendor/autoload.php';
