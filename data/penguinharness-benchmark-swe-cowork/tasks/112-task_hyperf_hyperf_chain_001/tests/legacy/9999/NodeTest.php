<?php

declare(strict_types=1);

use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testCoreConfigRemainsAutoloadable(): void
    {
        self::assertTrue(class_exists(\Hyperf\Config\Config::class));
    }
}
