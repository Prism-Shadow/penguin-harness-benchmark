<?php

declare(strict_types=1);

use ApiPlatform\Metadata\FilterInterface;
use ApiPlatform\Metadata\GraphQl\Query;
use ApiPlatform\Metadata\JsonSchemaFilterInterface;
use ApiPlatform\Metadata\Parameter;
use ApiPlatform\Metadata\QueryParameter;
use PHPUnit\Framework\TestCase;
use Psr\Container\ContainerInterface;

require_once __DIR__.'/../GraphQlFixture.php';

final class BehaviorTest extends TestCase
{
    use GraphQlFixture;

    public function testInlineAndServiceFiltersUseTheirSchemaThroughThePublicCollectionEntry(): void
    {
        foreach (['integer' => 'Int!', 'number' => 'Float!'] as $schemaType => $expected) {
            $filter = new class($schemaType) implements FilterInterface, JsonSchemaFilterInterface {
                public function __construct(private readonly string $schemaType)
                {
                }

                public function getDescription(string $resourceClass): array
                {
                    return [];
                }

                public function getSchema(Parameter $parameter): array
                {
                    return ['type' => $this->schemaType];
                }
            };
            foreach ([false, true] as $service) {
                $locator = $this->createMock(ContainerInterface::class);
                if ($service) {
                    $locator->expects(self::atLeastOnce())->method('has')->with('test.filter')->willReturn(true);
                    $locator->expects(self::atLeastOnce())->method('get')->with('test.filter')->willReturn($filter);
                } else {
                    $locator->expects(self::never())->method('has');
                    $locator->expects(self::never())->method('get');
                }
                $operation = new Query(name: 'collection_query', shortName: 'Book', class: stdClass::class, parameters: [
                    new QueryParameter(key: 'limit', property: 'count', required: true, filter: $service ? 'test.filter' : $filter),
                    new QueryParameter(key: 'label', schema: ['type' => 'string']),
                ]);
                $args = $this->collectionArguments($operation, $locator);
                self::assertSame($expected, (string) $args['limit']);
                self::assertSame('String', (string) $args['label']);
                self::assertArrayNotHasKey('count', $args);
            }
        }
    }
}
