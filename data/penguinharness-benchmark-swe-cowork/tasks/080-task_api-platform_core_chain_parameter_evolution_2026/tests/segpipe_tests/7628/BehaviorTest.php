<?php

declare(strict_types=1);

use ApiPlatform\Doctrine\Orm\Filter\UuidFilter;
use ApiPlatform\Metadata\QueryParameter;
use PHPUnit\Framework\TestCase;

require_once __DIR__.'/../StandaloneFilterFixture.php';

final class BehaviorTest extends TestCase
{
    use StandaloneFilterFixture;

    public function testUuidFilterPublishesScalarAndCollectionValidationSchemas(): void
    {
        self::assertTrue(class_exists(UuidFilter::class));

        $filter = new UuidFilter();
        $schema = $filter->getSchema(new QueryParameter(key: 'id'));
        $parameters = $filter->getOpenApiParameters(new QueryParameter(key: 'id'));

        self::assertSame('uuid', $schema['oneOf'][0]['format']);
        self::assertSame('uuid', $schema['oneOf'][1]['items']['format']);
        self::assertCount(2, $parameters);
        self::assertSame(['id', 'id[]'], array_map(static fn ($parameter) => $parameter->getName(), $parameters));
    }

    public function testUuidScalarAndCollectionValuesExecuteThroughTheExtension(): void
    {
        $manager = $this->datedManager();
        $a = '550e8400-e29b-41d4-a716-446655440000';
        $b = '550e8400-e29b-41d4-a716-446655440001';
        $manager->find(TaskDatedRecord::class, 1)->note = $a;
        $manager->find(TaskDatedRecord::class, 2)->note = $b;
        $manager->flush();
        $extension = new ApiPlatform\Doctrine\Orm\Extension\ParameterExtension($this->createStub(Psr\Container\ContainerInterface::class), $this->registryFor($manager));
        foreach ([[$a, [1]], [[$a, $b], [1, 2]], ['550e8400-e29b-41d4-a716-446655440099', []]] as [$value, $expected]) {
            $parameter = (new QueryParameter(key: 'id', property: 'note', filter: new UuidFilter()))->setValue($value);
            $operation = new ApiPlatform\Metadata\GetCollection(parameters: ['id' => $parameter]);
            $builder = $manager->createQueryBuilder()->select('r')->from(TaskDatedRecord::class, 'r')->orderBy('r.id');
            $extension->applyToCollection($builder, new ApiPlatform\Doctrine\Orm\Util\QueryNameGenerator(), TaskDatedRecord::class, $operation);
            self::assertSame($expected, array_map(static fn ($r) => $r->id, $builder->getQuery()->getResult()));
        }
    }
}
