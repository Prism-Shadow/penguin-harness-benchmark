<?php

declare(strict_types=1);

use Hyperf\Coroutine\Exception\ParallelExecutionException;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testParallelExceptionCarriesPartialResultsAndThrowables(): void
    {
        $failure = new RuntimeException('worker failed');
        $exception = new ParallelExecutionException('parallel operation failed');
        $exception->setResults(['first' => 10]);
        $exception->setThrowables(['second' => $failure]);

        self::assertSame(['first' => 10], $exception->getResults());
        self::assertSame($failure, $exception->getThrowables()['second']);
    }
}
