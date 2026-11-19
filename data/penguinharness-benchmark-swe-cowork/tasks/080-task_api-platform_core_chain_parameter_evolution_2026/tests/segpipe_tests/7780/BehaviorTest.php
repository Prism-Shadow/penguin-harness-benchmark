<?php

declare(strict_types=1);

use ApiPlatform\Doctrine\Odm\Filter\SortFilter;
use ApiPlatform\Metadata\QueryParameter;
use PHPUnit\Framework\TestCase;

require_once __DIR__.'/../NestedOdmFixture.php';

final class BehaviorTest extends TestCase
{
    use NestedOdmFixture;

    public function testOdmSortApplyUsesReferenceAndEmbeddedValuesWithStableTies(): void
    {
        $manager = $this->startOdmFixture();
        foreach ([
            ['department.name', 'asc', ['b-50', 'b-10', 'b-20', 'b-30', 'b-40']],
            ['department.name', 'DESC', ['b-20', 'b-30', 'b-40', 'b-10', 'b-50']],
            ['publisher.name', 'ASC', ['b-50', 'b-30', 'b-10', 'b-20', 'b-40']],
            ['profile.name', 'asc', ['b-50', 'b-40', 'b-10', 'b-20', 'b-30']],
            ['profile.name', 'desc', ['b-10', 'b-20', 'b-30', 'b-40', 'b-50']],
            ['department.name', 'sideways', ['b-10', 'b-20', 'b-30', 'b-40', 'b-50']],
            ['department.name', ['asc'], ['b-10', 'b-20', 'b-30', 'b-40', 'b-50']],
            ['department.name', null, ['b-10', 'b-20', 'b-30', 'b-40', 'b-50']],
        ] as [$property, $direction, $expected]) {
            $operation = $this->odmOperation($manager, [
                'sort' => (new QueryParameter(key: 'sort', property: $property, filter: new SortFilter()))->setValue($direction),
                'tie' => (new QueryParameter(key: 'tie', property: 'id', filter: new SortFilter()))->setValue('asc'),
            ]);
            $builder = $this->odmBuilder($manager, $operation);
            self::assertSame($expected, $this->odmIds($builder), json_encode([$property, $direction, $builder->getPipeline()]));
        }

        $this->odmDatabase->selectCollection('departments')->updateOne(['_id' => 'd-middle'], ['$set' => ['name' => 'zzz late']]);
        $operation = $this->odmOperation($manager, [
            'sort' => (new QueryParameter(key: 'sort', property: 'department.name', filter: new SortFilter()))->setValue('asc'),
            'tie' => (new QueryParameter(key: 'tie', property: 'id', filter: new SortFilter()))->setValue('asc'),
        ]);
        self::assertSame(['b-10', 'b-20', 'b-30', 'b-40', 'b-50'], $this->odmIds($this->odmBuilder($manager, $operation)));
    }

    public function testOdmSortPreservesPriorityAcrossDifferentLookupAliases(): void
    {
        $manager = $this->startOdmFixture();
        foreach ([
            [['department.name', 'publisher.name'], ['b-50', 'b-10', 'b-30', 'b-20', 'b-40']],
            [['publisher.name', 'department.name'], ['b-50', 'b-30', 'b-10', 'b-20', 'b-40']],
        ] as [$properties, $expected]) {
            $parameters = [];
            foreach ([...$properties, 'id'] as $index => $property) {
                $key = 'sort'.$index;
                $parameters[$key] = (new QueryParameter(key: $key, property: $property, filter: new SortFilter()))->setValue('asc');
            }
            $operation = $this->odmOperation($manager, $parameters);
            $builder = $this->odmBuilder($manager, $operation);
            self::assertSame($expected, $this->odmIds($builder), json_encode($builder->getPipeline()));
        }
    }

    public function testOdmParameterSortFilterExposesItsDirectionContract(): void
    {
        self::assertTrue(class_exists(SortFilter::class));

        $filter = new SortFilter();
        self::assertSame(
            ['type' => 'string', 'enum' => ['asc', 'desc', 'ASC', 'DESC']],
            $filter->getSchema(new QueryParameter(key: 'sort', property: 'department.name')),
        );
    }
}
