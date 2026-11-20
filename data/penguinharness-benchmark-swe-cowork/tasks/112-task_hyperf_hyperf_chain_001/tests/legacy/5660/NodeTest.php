<?php

declare(strict_types=1);

use Hyperf\Codec\Base62;
use Hyperf\Codec\Exception\InvalidArgumentException;
use Hyperf\Codec\Json;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testCodecRoundTripsValuesAndTranslatesJsonErrors(): void
    {
        self::assertSame('zz', Base62::encode(3843));
        self::assertSame(3843, Base62::decode('zz'));
        self::assertSame(['name' => 'Hyperf', 'enabled' => true], Json::decode(Json::encode([
            'name' => 'Hyperf',
            'enabled' => true,
        ])));

        $raised = null;
        try {
            Json::decode('{invalid json');
        } catch (InvalidArgumentException $exception) {
            $raised = $exception;
        }

        self::assertInstanceOf(InvalidArgumentException::class, $raised);
        self::assertInstanceOf(JsonException::class, $raised->getPrevious());
    }
}
