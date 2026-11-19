<?php

declare(strict_types=1);

use Composer\Autoload\ClassLoader;
use Hyperf\Support\Composer;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testSupportComposerReadsTheActiveProjectManifestAndLoader(): void
    {
        $manifest = Composer::getJsonContent();

        self::assertSame('hyperf/hyperf', $manifest->get('name'));
        self::assertArrayHasKey('autoload', $manifest->all());
        self::assertInstanceOf(ClassLoader::class, Composer::getLoader());
    }
}
