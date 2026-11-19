<?php

declare(strict_types=1);

use Hyperf\Pool\Channel;
use PHPUnit\Framework\TestCase;
use SegpipeTask\Tests\BlocksLegacyDependencies;
use SegpipeTask\Tests\TestConnection;

final class NodeTest extends TestCase
{
    use BlocksLegacyDependencies;

    public function testPoolChannelUsesCoroutineComponentAtItsBoundary(): void
    {
        $this->blockLegacyDependencies(Hyperf\Utils\Coroutine::class);
        $channel = new Channel(2);
        $connection = new TestConnection();

        self::assertTrue($channel->push($connection));
        self::assertSame(1, $channel->length());
        self::assertSame($connection, $channel->pop(0.01));
        self::assertSame(0, $channel->length());
    }
}
