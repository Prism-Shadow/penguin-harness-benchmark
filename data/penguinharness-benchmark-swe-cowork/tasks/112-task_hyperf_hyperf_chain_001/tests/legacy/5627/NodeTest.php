<?php

declare(strict_types=1);

use Hyperf\Context\Context;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testDestroyRemovesTheRequestedValueInsideACoroutine(): void
    {
        $state = null;
        Swoole\Coroutine\run(static function () use (&$state): void {
            Context::set('request.trace', 'trace-123');
            $before = Context::get('request.trace');
            Context::destroy('request.trace');
            $state = [$before, Context::has('request.trace'), Context::get('request.trace', 'missing')];
        });

        self::assertSame(['trace-123', false, 'missing'], $state);
    }
}
