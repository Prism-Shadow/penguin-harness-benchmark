<?php

declare(strict_types=1);

use Hyperf\Retry\BackoffStrategy;
use PHPUnit\Framework\TestCase;
use SegpipeTask\Tests\BlocksLegacyDependencies;

final class NodeTest extends TestCase
{
    use BlocksLegacyDependencies;

    public function testRetryStrategyUsesSupportBackoffWithoutLegacyUtils(): void
    {
        $this->blockLegacyDependencies(Hyperf\Utils\Backoff::class);
        $strategy = new BackoffStrategy(0);
        $startedAt = microtime(true);
        $strategy->sleep();

        self::assertInstanceOf(BackoffStrategy::class, $strategy);
        self::assertLessThan(0.2, microtime(true) - $startedAt);
    }
}
