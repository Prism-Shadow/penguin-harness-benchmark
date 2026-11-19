<?php

declare(strict_types=1);

use ApiPlatform\GraphQl\Resolver\Factory\ResolverFactoryInterface;
use ApiPlatform\GraphQl\Type\ContextAwareTypeBuilderInterface;
use ApiPlatform\GraphQl\Type\FieldsBuilder;
use ApiPlatform\GraphQl\Type\TypeConverter;
use ApiPlatform\GraphQl\Type\TypesContainer;
use ApiPlatform\Metadata\ApiResource;
use ApiPlatform\Metadata\GraphQl\Query;
use ApiPlatform\Metadata\Property\Factory\PropertyMetadataFactoryInterface;
use ApiPlatform\Metadata\Property\Factory\PropertyNameCollectionFactoryInterface;
use ApiPlatform\Metadata\Resource\Factory\ResourceMetadataCollectionFactoryInterface;
use ApiPlatform\Metadata\Resource\ResourceMetadataCollection;
use ApiPlatform\Metadata\ResourceClassResolverInterface;
use ApiPlatform\State\Pagination\Pagination;
use GraphQL\Type\Definition\ObjectType;
use GraphQL\Type\Definition\Type;
use Psr\Container\ContainerInterface;

trait GraphQlFixture
{
    private function collectionArguments(Query $operation, ContainerInterface $locator): array
    {
        $operation = $operation->withPaginationEnabled(false);
        $metadata = $this->createStub(ResourceMetadataCollectionFactoryInterface::class);
        $metadata->method('create')->willReturn(new ResourceMetadataCollection(stdClass::class, [
            new ApiResource(shortName: 'Book', graphQlOperations: ['collection_query' => $operation]),
        ]));
        $properties = $this->createStub(PropertyMetadataFactoryInterface::class);
        $resolver = $this->createStub(ResourceClassResolverInterface::class);
        $resolver->method('isResourceClass')->willReturn(true);
        $types = new TypesContainer();
        $typeBuilder = $this->createStub(ContextAwareTypeBuilderInterface::class);
        $typeBuilder->method('getResourceObjectType')->willReturn(new ObjectType([
            'name' => 'Book', 'fields' => ['id' => Type::id()],
        ]));
        $resolvers = $this->createStub(ResolverFactoryInterface::class);
        $resolvers->method('__invoke')->willReturn(static fn () => []);
        $builder = new FieldsBuilder(
            $this->createStub(PropertyNameCollectionFactoryInterface::class),
            $properties,
            $metadata,
            $resolver,
            $types,
            $typeBuilder,
            new TypeConverter($typeBuilder, $types, $metadata, $properties),
            $resolvers,
            $locator,
            new Pagination(),
            null,
            '__',
        );

        $fields = $builder->getCollectionQueryFields(stdClass::class, $operation, []);
        self::assertArrayHasKey('books', $fields);
        $root = new ObjectType(['name' => 'Query', 'fields' => $fields]);
        $arguments = [];
        foreach ($root->getField('books')->args as $argument) {
            $arguments[$argument->name] = $argument->getType();
        }

        return $arguments;
    }
}
