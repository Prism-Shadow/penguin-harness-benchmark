<?php

declare(strict_types=1);

use Hyperf\Codec\Packer\JsonPacker;
use Hyperf\Codec\Packer\PhpSerializerPacker;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testExtractedPackersRoundTripStructuredAndTypedPayloads(): void
    {
        $json = new JsonPacker();
        $payload = ['message' => '你好', 'count' => 3];
        self::assertSame($payload, $json->unpack($json->pack($payload)));

        $php = new PhpSerializerPacker();
        $typed = (object) ['id' => 91, 'active' => true];
        self::assertEquals($typed, $php->unpack($php->pack($typed)));
    }
}
