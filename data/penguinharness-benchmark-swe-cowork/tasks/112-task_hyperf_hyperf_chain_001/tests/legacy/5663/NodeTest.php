<?php

declare(strict_types=1);

use Hyperf\Serializer\JsonDeNormalizer;
use Hyperf\Serializer\SimpleNormalizer;
use PHPUnit\Framework\TestCase;

final class SerializableValueForNode5663
{
    public static function jsonDeSerialize(array $data): self
    {
        $value = new self();
        $value->number = (int) $data['number'];
        return $value;
    }

    public int $number;
}

final class NodeTest extends TestCase
{
    public function testSerializerNormalizersPreserveAndDenormalizeValues(): void
    {
        $simple = new SimpleNormalizer();
        self::assertSame(12, $simple->denormalize('12', 'int'));
        self::assertSame(['x' => 1], $simple->normalize(['x' => 1]));

        $json = new JsonDeNormalizer();
        $value = $json->denormalize(['number' => '27'], SerializableValueForNode5663::class);
        self::assertInstanceOf(SerializableValueForNode5663::class, $value);
        self::assertSame(27, $value->number);
    }
}
