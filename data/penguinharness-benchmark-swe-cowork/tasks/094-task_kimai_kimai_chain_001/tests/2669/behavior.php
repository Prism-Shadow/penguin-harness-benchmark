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

$stat = new App\Model\CustomerStatistic();
$stat->setRecordAmount(2);
$stat->setRecordDuration(3600);
$stat->setRecordRate(12.5);
behavior_assert($stat->getRecordAmount() === 2 && $stat->getRecordDuration() === 3600, 'customer statistic counters failed');
