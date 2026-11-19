<?php

declare(strict_types=1);

use Hyperf\Pipeline\Pipeline;
use PHPUnit\Framework\TestCase;
use SegpipeTask\Tests\TestContainer;

final class NodeTest extends TestCase
{
    public function testStandalonePipelinePreservesOrderAndReturnValue(): void
    {
        $pipeline = new Pipeline(new TestContainer());
        $result = $pipeline->send('start')
            ->through(
                static fn (string $value, Closure $next) => $next($value . ':first'),
                static fn (string $value, Closure $next) => $next($value . ':second')
            )
            ->via('handle')
            ->thenReturn();

        self::assertSame('start:first:second', $result);

        $objectPipe = new class {
            public function transform(string $value, Closure $next): string
            {
                return $next($value . ':object');
            }
        };
        $viaResult = $pipeline->send('start')
            ->through($objectPipe)
            ->via('transform')
            ->thenReturn();

        self::assertSame('start:object', $viaResult);
    }
}
