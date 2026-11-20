<?php

declare(strict_types=1);

use Hyperf\Stringable\Str;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testStandaloneStringableSupportsFluentAndUnicodeOperations(): void
    {
        $value = Str::of('  Hyperf  ')->trim()->append(' Framework')->lower();

        self::assertSame('hyperf framework', (string) $value);
        self::assertSame('你**界', Str::mask('你好世界', 1, 2));
        self::assertTrue(Str::of('cumulative migration')->containsAll(['cumulative', 'migration']));
    }
}
