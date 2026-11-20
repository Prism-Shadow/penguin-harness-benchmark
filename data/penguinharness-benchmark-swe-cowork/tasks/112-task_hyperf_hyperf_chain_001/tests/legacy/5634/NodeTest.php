<?php

declare(strict_types=1);

use Hyperf\Cache\Helper\StringHelper;
use PHPUnit\Framework\TestCase;
use SegpipeTask\Tests\BlocksLegacyDependencies;

final class NodeTest extends TestCase
{
    use BlocksLegacyDependencies;

    public function testCacheKeysUseStringablePackageForNestedInterpolation(): void
    {
        $this->blockLegacyDependencies(Hyperf\Utils\Str::class);
        $arguments = ['tenant' => ['id' => 8], 'record' => ['id' => 21]];

        self::assertSame('cache:tenant-8:record-21', StringHelper::format(
            'cache',
            $arguments,
            'tenant-#{tenant.id}:record-#{record.id}'
        ));
        self::assertSame(['#{tenant.id}', '#{record.id}'], StringHelper::parse('#{tenant.id}/#{record.id}'));
    }
}
