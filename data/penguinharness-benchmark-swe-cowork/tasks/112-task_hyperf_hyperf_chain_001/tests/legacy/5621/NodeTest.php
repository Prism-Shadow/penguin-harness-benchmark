<?php

declare(strict_types=1);

use Hyperf\Config\Config;
use Hyperf\Context\ApplicationContext;
use Hyperf\Contract\ConfigInterface;
use PHPUnit\Framework\TestCase;
use SegpipeTask\Tests\BlocksLegacyDependencies;
use SegpipeTask\Tests\TestContainer;

final class NodeTest extends TestCase
{
    use BlocksLegacyDependencies;

    public function testGlobalConfigUsesContextPackageContainer(): void
    {
        $this->blockLegacyDependencies(Hyperf\Utils\ApplicationContext::class);
        ApplicationContext::setContainer(new TestContainer([
            ConfigInterface::class => new Config(['service' => ['timeout' => 15]]),
        ]));

        self::assertSame(15, config('service.timeout'));
        self::assertSame('fallback', config('service.missing', 'fallback'));
    }
}
