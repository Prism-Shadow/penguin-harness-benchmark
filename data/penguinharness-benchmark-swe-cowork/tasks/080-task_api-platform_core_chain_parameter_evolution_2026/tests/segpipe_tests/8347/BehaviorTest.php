<?php

declare(strict_types=1);

use ApiPlatform\Doctrine\Orm\Filter\SortFilter;
use ApiPlatform\Metadata\GraphQl\Query;
use ApiPlatform\Metadata\QueryParameter;
use GraphQL\Type\Definition\InputObjectType;
use GraphQL\Type\Definition\ListOfType;
use PHPUnit\Framework\TestCase;
use Psr\Container\ContainerInterface;

require_once __DIR__.'/../GraphQlFixture.php';

final class BehaviorTest extends TestCase
{
    use GraphQlFixture;

    public function testSortParametersMergeIntoAListWithoutCapturingScalarArguments(): void
    {
        foreach ([['name', 'rank'], ['rank', 'name']] as $properties) {
            $locator = $this->createMock(ContainerInterface::class);
            $locator->expects(self::never())->method('get');
            $parameters = [];
            foreach ($properties as $property) {
                $parameters[] = new QueryParameter(key: 'order['.$property.']', property: $property, filter: new SortFilter());
            }
            $parameters[] = new QueryParameter(key: 'department.code', schema: ['type' => 'string'], required: true);
            $parameters[] = new QueryParameter(key: 'enabled', schema: ['type' => 'boolean']);
            $args = $this->collectionArguments(new Query(
                name: 'collection_query', shortName: 'Book', class: stdClass::class, parameters: $parameters,
            ), $locator);

            self::assertInstanceOf(ListOfType::class, $args['order']);
            $input = $args['order']->getWrappedType();
            self::assertInstanceOf(InputObjectType::class, $input);
            self::assertCount(2, $input->getFields());
            foreach ($properties as $property) {
                self::assertSame('String', (string) $input->getField($property)->getType());
            }
            self::assertSame('String!', (string) $args['department__code']);
            self::assertSame('Boolean', (string) $args['enabled']);
            self::assertArrayNotHasKey('order[name]', $args);
        }
    }
}
