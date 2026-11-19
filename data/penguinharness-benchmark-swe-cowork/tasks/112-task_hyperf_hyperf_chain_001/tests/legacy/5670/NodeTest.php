<?php

declare(strict_types=1);

use Hyperf\CodeParser\PhpParser;
use Hyperf\CodeParser\Exception\InvalidArgumentException;
use PhpParser\Node\Expr\Array_;
use PhpParser\Node\Scalar\LNumber;
use PhpParser\Node\Scalar\String_;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testCodeParserBuildsTypedAstForAssociativeValues(): void
    {
        $expression = (new PhpParser())->getExprFromValue(['answer' => 42]);

        self::assertInstanceOf(Array_::class, $expression);
        self::assertCount(1, $expression->items);
        self::assertInstanceOf(String_::class, $expression->items[0]->key);
        self::assertSame('answer', $expression->items[0]->key->value);
        self::assertInstanceOf(LNumber::class, $expression->items[0]->value);
        self::assertSame(42, $expression->items[0]->value->value);

        $resource = fopen('php://memory', 'r');
        $raised = null;
        try {
            (new PhpParser())->getExprFromValue($resource);
        } catch (InvalidArgumentException $exception) {
            $raised = $exception;
        } finally {
            fclose($resource);
        }

        self::assertInstanceOf(InvalidArgumentException::class, $raised);
    }
}
