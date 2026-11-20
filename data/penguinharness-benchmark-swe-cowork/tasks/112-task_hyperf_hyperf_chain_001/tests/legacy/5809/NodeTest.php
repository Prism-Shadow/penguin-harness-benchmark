<?php

declare(strict_types=1);

use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testHelperComponentProvidesGlobalCompatibilityFunctions(): void
    {
        $helperFile = BASE_PATH . '/src/helper/src/Functions.php';
        if (! is_file($helperFile)) {
            self::fail('The standalone helper component is unavailable.');
        }
        require_once $helperFile;

        self::assertSame('getUserId', getter('user_id'));
        self::assertSame('setRequestId', setter('request_id'));
        self::assertSame('Hyperf', optional((object) ['name' => 'Hyperf'])->name);
        self::assertSame(8, value(static fn (int $number): int => $number * 2, 4));
    }
}
