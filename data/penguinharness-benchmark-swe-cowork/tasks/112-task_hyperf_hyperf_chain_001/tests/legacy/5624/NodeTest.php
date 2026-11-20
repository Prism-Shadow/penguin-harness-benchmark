<?php

declare(strict_types=1);

use Hyperf\Coroutine\Channel\Manager;
use Hyperf\Engine\Channel;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testChannelManagerInitializesReusesClosesAndFlushesChannels(): void
    {
        $manager = new Manager(2);
        $first = $manager->get(7, true);

        self::assertInstanceOf(Channel::class, $first);
        self::assertSame($first, $manager->get(7));
        self::assertNull($manager->get(8));
        $manager->get(8, true);
        self::assertCount(2, $manager->getChannels());

        $manager->close(7);
        self::assertNull($manager->get(7));
        $manager->flush();
        self::assertSame([], $manager->getChannels());
    }
}
