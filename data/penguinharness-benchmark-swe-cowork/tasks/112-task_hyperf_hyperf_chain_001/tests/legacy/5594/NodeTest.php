<?php

declare(strict_types=1);

use Hyperf\Config\Config;
use PHPUnit\Framework\TestCase;
use SegpipeTask\Tests\BlocksLegacyDependencies;

final class NodeTest extends TestCase
{
    use BlocksLegacyDependencies;

    public function testConfigNestedAccessDoesNotLoadLegacyUtilsArr(): void
    {
        $this->blockLegacyDependencies(Hyperf\Utils\Arr::class);
        $config = new Config(['database' => ['primary' => ['host' => 'db.internal']]]);

        self::assertTrue($config->has('database.primary.host'));
        self::assertSame('db.internal', $config->get('database.primary.host'));
        $config->set('database.primary.port', 5432);
        self::assertSame(5432, $config->get('database.primary.port'));
    }
}
