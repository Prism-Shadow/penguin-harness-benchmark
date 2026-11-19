<?php

declare(strict_types=1);

use ApiPlatform\Doctrine\Orm\Filter\ExactFilter;
use ApiPlatform\Doctrine\Orm\Util\QueryNameGenerator;
use ApiPlatform\Metadata\Exception\InvalidArgumentException;
use ApiPlatform\Metadata\QueryParameter;
use PHPUnit\Framework\TestCase;

final class BehaviorTest extends TestCase
{
    public function testMissingFilterPropertyHasAnApiLevelDiagnostic(): void
    {
        foreach (['status', 'visibility'] as $key) {
            $parameter = (new QueryParameter(key: $key))->setValue('active');
            $builder = task_query_builder();
            $before = $builder->getDQL();
            try {
                (new ExactFilter())->apply($builder, new QueryNameGenerator(), stdClass::class, context: ['parameter' => $parameter]);
                self::fail('A missing target property must be rejected.');
            } catch (InvalidArgumentException $exception) {
                self::assertStringContainsString($key, $exception->getMessage());
                self::assertSame($before, $builder->getDQL());
                self::assertCount(0, $builder->getParameters());
            }
        }
    }
}
