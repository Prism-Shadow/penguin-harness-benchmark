<?php

declare(strict_types=1);

use Hyperf\Coroutine\Channel\Pool;
use Hyperf\GrpcClient\GrpcClient;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testGrpcClientAcceptsTheCoroutineChannelPoolContract(): void
    {
        $pool = new Pool();
        $client = new GrpcClient($pool);
        $client->set('http://127.0.0.1:9501', ['timeout' => 0.25]);

        self::assertInstanceOf(GrpcClient::class, $client);
        self::assertSame(0, $pool->count());
    }
}
