<?php

declare(strict_types=1);

use ApiPlatform\Doctrine\Orm\Filter\FilterInterface;
use ApiPlatform\Doctrine\Orm\Filter\FreeTextQueryFilter;
use ApiPlatform\Doctrine\Orm\Util\QueryNameGenerator;
use ApiPlatform\Doctrine\Orm\Util\QueryNameGeneratorInterface;
use ApiPlatform\Metadata\Operation;
use ApiPlatform\Metadata\QueryParameter;
use Doctrine\ORM\QueryBuilder;
use PHPUnit\Framework\TestCase;

require_once __DIR__.'/../NestedOrmFixture.php';
require_once __DIR__.'/../NestedOdmFixture.php';

final class BehaviorTest extends TestCase
{
    use NestedOrmFixture;
    use NestedOdmFixture;

    public function testOdmMetadataExtensionAndFreeTextReturnReferenceEmbeddedAndFlatMatches(): void
    {
        $manager = $this->startOdmFixture();
        foreach ([
            [['department.name', 'title'], ['b-10', 'b-20']],
            [['title', 'department.name'], ['b-10', 'b-20']],
            [['department.name', 'publisher.name'], ['b-10', 'b-30']],
            [['publisher.name', 'department.name'], ['b-10', 'b-30']],
            [['profile.name', 'title'], ['b-20', 'b-40']],
            [['title', 'profile.name'], ['b-20', 'b-40']],
            [['department.name', 'profile.name'], ['b-10', 'b-40']],
            [['profile.name', 'department.name'], ['b-10', 'b-40']],
        ] as [$properties, $expected]) {
            foreach (['needle', 'absent', 'needle.*'] as $value) {
                $filter = new \ApiPlatform\Doctrine\Odm\Filter\FreeTextQueryFilter(new \ApiPlatform\Doctrine\Odm\Filter\PartialSearchFilter());
                $operation = $this->odmOperation($manager, [
                    'q' => (new QueryParameter(key: 'q', properties: $properties, filter: $filter))->setValue($value),
                ]);
                $before = $operation->getParameters()->get('q')->getExtraProperties();
                $context = ['operator' => 'addOr'];
                $builder = $this->odmBuilder($manager, $operation, $context);
                $builder->sort(['_id' => 1]);
                self::assertSame('needle' === $value ? $expected : [], $this->odmIds($builder), json_encode([$properties, $value, $builder->getPipeline()]));
                self::assertSame($before, $operation->getParameters()->get('q')->getExtraProperties());
            }
        }

        $this->odmDatabase->selectCollection('books')->updateOne(['_id' => 'b-50'], ['$set' => ['title' => 'needle']]);
        $operation = $this->odmOperation($manager, [
            'q' => (new QueryParameter(key: 'q', properties: ['department.name', 'title'], filter: new \ApiPlatform\Doctrine\Odm\Filter\FreeTextQueryFilter(new \ApiPlatform\Doctrine\Odm\Filter\PartialSearchFilter())))->setValue('needle'),
        ]);
        $context = ['operator' => 'addOr'];
        $builder = $this->odmBuilder($manager, $operation, $context);
        $builder->sort(['_id' => 1]);
        self::assertSame(['b-10', 'b-20', 'b-50'], $this->odmIds($builder));
        $this->odmDatabase->selectCollection('departments')->updateOne(['_id' => 'd-needle'], ['$set' => ['name' => 'retired']]);
        $context = ['operator' => 'addOr'];
        $builder = $this->odmBuilder($manager, $operation, $context);
        $builder->sort(['_id' => 1]);
        self::assertSame(['b-20', 'b-50'], $this->odmIds($builder));
    }

    public function testOdmFreeTextDelegationMatchesIndependentlyPreparedPropertyMetadata(): void
    {
        foreach ([
            ['department.name', 'title'], ['title', 'department.name'],
            ['department.name', 'publisher.name'], ['publisher.name', 'department.name'],
        ] as $properties) {
            $seen = new ArrayObject();
            $inner = new class($seen) implements \ApiPlatform\Doctrine\Odm\Filter\FilterInterface {
                public function __construct(private readonly ArrayObject $seen)
                {
                }

                public function apply(\Doctrine\ODM\MongoDB\Aggregation\Builder $builder, string $resourceClass, ?Operation $operation = null, array &$context = []): void
                {
                    $parameter = $context['parameter'];
                    $this->seen[$parameter->getProperty()] = [
                        $parameter->getValue(),
                        $parameter->getExtraProperties()['nested_properties_info'] ?? [],
                    ];
                }

                public function getDescription(string $resourceClass): array
                {
                    return [];
                }
            };
            $filter = new \ApiPlatform\Doctrine\Odm\Filter\FreeTextQueryFilter($inner);
            $operation = $this->nestedOperation($properties, $filter, 'needle');
            $parameter = $operation->getParameters()->get('q');
            $before = $parameter->getExtraProperties();
            $context = ['parameter' => $parameter, 'match' => $this->createStub(\Doctrine\ODM\MongoDB\Aggregation\Expr::class)];
            $filter->apply($this->createStub(\Doctrine\ODM\MongoDB\Aggregation\Builder::class), TaskNestedBook::class, $operation, $context);

            foreach ($properties as $property) {
                $single = $this->nestedOperation([$property], $inner, 'needle')->getParameters()->get('q');
                self::assertSame(['needle', $single->getExtraProperties()['nested_properties_info'] ?? []], $seen[$property]);
            }
            self::assertSame($before, $parameter->getExtraProperties());
            self::assertSame($properties, array_keys($seen->getArrayCopy()));
        }
    }

    public function testMetadataExtensionAndFreeTextExecuteJoinedSqlWithoutCrossPropertyLeakage(): void
    {
        $manager = $this->nestedEntityManager();
        $locator = $this->createStub(\Psr\Container\ContainerInterface::class);
        $extension = new \ApiPlatform\Doctrine\Orm\Extension\ParameterExtension($locator);
        foreach ([
            [['department.name', 'title'], [1, 2]],
            [['title', 'department.name'], [1, 2]],
            [['department.name', 'publisher.name'], [1, 3]],
            [['publisher.name', 'department.name'], [1, 3]],
        ] as [$properties, $expected]) {
            foreach (['needle', 'absent'] as $value) {
                $filter = new FreeTextQueryFilter(new \ApiPlatform\Doctrine\Orm\Filter\PartialSearchFilter());
                $operation = $this->nestedOperation($properties, $filter, $value);
                $builder = $manager->createQueryBuilder()->select('book')->from(TaskNestedBook::class, 'book')->orderBy('book.id');
                $extension->applyToCollection($builder, new QueryNameGenerator(), TaskNestedBook::class, $operation, ['whereClause' => 'orWhere']);
                $rows = $builder->getQuery()->getResult();
                self::assertSame('needle' === $value ? $expected : [], array_map(static fn (TaskNestedBook $book): int => $book->id, $rows));
            }
        }
        $manager->find(TaskNestedBook::class, 4)->title = 'needle';
        $manager->flush();
        $operation = $this->nestedOperation(['department.name', 'title'], new FreeTextQueryFilter(new \ApiPlatform\Doctrine\Orm\Filter\PartialSearchFilter()), 'needle');
        $builder = $manager->createQueryBuilder()->select('book')->from(TaskNestedBook::class, 'book')->orderBy('book.id');
        $extension->applyToCollection($builder, new QueryNameGenerator(), TaskNestedBook::class, $operation, ['whereClause' => 'orWhere']);
        self::assertSame([1, 2, 4], array_map(static fn (TaskNestedBook $book): int => $book->id, $builder->getQuery()->getResult()));
    }

    public function testEachFreeTextSubParameterReceivesOnlyItsOwnNestedMetadata(): void
    {
        $seen = new ArrayObject();
        $inner = new class($seen) implements FilterInterface {
            public function __construct(private readonly ArrayObject $seen)
            {
            }

            public function apply(QueryBuilder $queryBuilder, QueryNameGeneratorInterface $queryNameGenerator, string $resourceClass, ?Operation $operation = null, array $context = []): void
            {
                $parameter = $context['parameter'];
                $this->seen[$parameter->getProperty()] = $parameter->getExtraProperties()['nested_properties_info'] ?? null;
                $queryBuilder->andWhere('1 = 1');
            }

            public function getDescription(string $resourceClass): array
            {
                return [];
            }
        };
        $nested = [
            'relation_segments' => ['department'],
            'converted_relation_segments' => ['department'],
            'relation_classes' => [stdClass::class],
            'leaf_property' => 'name',
            'leaf_class' => stdClass::class,
        ];
        $parameter = (new QueryParameter(
            key: 'q',
            properties: ['department.name', 'title'],
            extraProperties: ['nested_properties_info' => ['department.name' => $nested]],
        ))->setValue('needle');

        (new FreeTextQueryFilter($inner))->apply(
            task_query_builder(),
            new QueryNameGenerator(),
            stdClass::class,
            context: ['parameter' => $parameter],
        );

        self::assertSame(['department.name' => $nested], $seen['department.name']);
        self::assertSame([], $seen['title']);
    }
}
