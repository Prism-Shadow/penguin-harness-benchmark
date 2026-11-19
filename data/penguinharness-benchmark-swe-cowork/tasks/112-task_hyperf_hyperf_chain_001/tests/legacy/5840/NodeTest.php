<?php

declare(strict_types=1);

use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testCoroutineComponentOwnsGlobalGoCoAndDeferHelpers(): void
    {
        $helperFile = BASE_PATH . '/src/coroutine/src/Helper.php';
        if (! is_file($helperFile)) {
            self::fail('Coroutine global helper bootstrap is unavailable.');
        }
        require_once $helperFile;

        self::assertTrue(function_exists('go'));
        self::assertTrue(function_exists('co'));
        self::assertTrue(function_exists('defer'));

        $events = [];
        Swoole\Coroutine\run(static function () use (&$events): void {
            $channel = new Swoole\Coroutine\Channel(2);
            defer(static function () use (&$events): void {
                $events[] = 'deferred';
            });
            $goId = go(static fn () => $channel->push('go'));
            $coId = co(static fn () => $channel->push('co'));
            $events[] = $channel->pop(1.0);
            $events[] = $channel->pop(1.0);
            $events[] = is_int($goId) && is_int($coId) ? 'ids' : 'bad-ids';
        });

        self::assertContains('go', $events);
        self::assertContains('co', $events);
        self::assertContains('ids', $events);
        self::assertSame('deferred', end($events));
    }
}
