<?php

declare(strict_types=1);

use Hyperf\Context\ApplicationContext;
use PHPUnit\Framework\TestCase;
use SegpipeTask\Tests\TestContainer;

final class NodeTest extends TestCase
{
    public function testContextPackageOwnsApplicationContainerState(): void
    {
        $container = new TestContainer(['answer' => 42]);

        self::assertSame($container, ApplicationContext::setContainer($container));
        self::assertTrue(ApplicationContext::hasContainer());
        self::assertSame($container, ApplicationContext::getContainer());
        self::assertSame(42, ApplicationContext::getContainer()->get('answer'));
    }
}
