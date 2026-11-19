<?php

declare(strict_types=1);

use PHPUnit\Framework\TestCase;

use function Hyperf\Support\optional;
use function Hyperf\Support\retry;
use function Hyperf\Support\value;

final class NodeTest extends TestCase
{
    public function testSupportFunctionsHandleLazyValuesNullsAndRetryBoundaries(): void
    {
        self::assertSame(12, value(static fn (int $input): int => $input * 3, 4));
        self::assertNull(optional(null)->missing);
        self::assertSame('Hyperf', optional((object) ['name' => 'Hyperf'])->name);

        $attempts = 0;
        $result = retry(1, static function (int $attempt) use (&$attempts): string {
            ++$attempts;
            if ($attempt === 1) {
                throw new RuntimeException('retry once');
            }
            return 'recovered';
        });
        self::assertSame('recovered', $result);
        self::assertSame(2, $attempts);
    }
}
