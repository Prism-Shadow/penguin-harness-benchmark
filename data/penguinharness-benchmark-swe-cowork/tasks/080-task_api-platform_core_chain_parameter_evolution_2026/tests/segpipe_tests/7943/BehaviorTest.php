<?php

declare(strict_types=1);

use ApiPlatform\Metadata\ApiResource;
use ApiPlatform\Metadata\Get;
use ApiPlatform\Metadata\Link;
use ApiPlatform\Metadata\Resource\Factory\ResourceMetadataCollectionFactoryInterface;
use ApiPlatform\Metadata\Resource\ResourceMetadataCollection;
use ApiPlatform\State\Exception\ProviderNotFoundException;
use ApiPlatform\State\ParameterProvider\ReadLinkParameterProvider;
use ApiPlatform\State\ProviderInterface;
use PHPUnit\Framework\TestCase;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

final class BehaviorTest extends TestCase
{
    public function testProvideScopesScalarValuesAndPreservesStructuredIdentifiers(): void
    {
        $foo = new Link(fromClass: 'App\\Resource\\Foo');
        $bar = new Link(fromClass: 'App\\Resource\\Bar');
        foreach ([['fooId' => $foo, 'barId' => $bar], ['barId' => $bar, 'fooId' => $foo]] as $links) {
            $this->assertMapping($links, 'B-17', [['barId' => 'B-17']]);
        }
        $this->assertMapping(['fooId' => $foo], 'B-17', [[]]);
        $this->assertMapping([], 'B-17', [[]]);
        $this->assertMapping(['fooId' => $foo], ['already' => 'mapped'], [['already' => 'mapped']]);
        $this->assertMapping(['barId' => $bar], ['B-17', 'B-18'], [['barId' => 'B-17'], ['barId' => 'B-18']]);
        $this->assertMapping([new Link(toClass: 'App\\Resource\\Bar', parameterName: 'barKey')], 0, [['barKey' => 0]]);
    }

    private function assertMapping(array $links, mixed $input, array $expected): void
    {
        $target = new Get(class: 'App\\Resource\\Bar', uriVariables: $links);
        $factory = $this->createMock(ResourceMetadataCollectionFactoryInterface::class);
        $factory->expects(self::once())->method('create')->with('App\\Resource\\Bar')
            ->willReturn(new ResourceMetadataCollection('App\\Resource\\Bar', [new ApiResource(operations: ['read' => $target])]));
        $calls = [];
        $entity = new stdClass();
        $locator = $this->createMock(ProviderInterface::class);
        $locator->expects(self::exactly(count($expected)))->method('provide')->willReturnCallback(
            static function ($operation, $variables, $context) use (&$calls, $target, $entity) {
                self::assertSame($target, $operation);
                $calls[] = $variables;
                return $entity;
            }
        );
        $parameter = (new Link(key: 'bar', fromClass: 'App\\Resource\\Bar'))->setValue($input);
        $request = new Request();
        $original = new Get(class: 'App\\Resource\\Foo', uriVariables: []);
        $result = (new ReadLinkParameterProvider($locator, $factory))->provide($parameter, context: ['operation' => $original, 'request' => $request]);
        self::assertSame($expected, $calls);
        $resolved = is_array($input) && array_is_list($input) ? array_fill(0, count($input), $entity) : $entity;
        self::assertSame($resolved, $parameter->getValue());
        self::assertSame($resolved, $request->attributes->get('bar'));
        self::assertSame($parameter, $result->getUriVariables()['bar']);
        self::assertSame([], $original->getUriVariables());
    }

    public function testMissingProviderHonorsThrowNotFound(): void
    {
        foreach ([false, true] as $throws) {
            $target = new Get(class: 'App\\Resource\\Bar', uriVariables: ['barId' => new Link(fromClass: 'App\\Resource\\Bar')]);
            $factory = $this->createStub(ResourceMetadataCollectionFactoryInterface::class);
            $factory->method('create')->willReturn(new ResourceMetadataCollection('App\\Resource\\Bar', [new ApiResource(operations: ['read' => $target])]));
            $locator = $this->createStub(ProviderInterface::class);
            $locator->method('provide')->willThrowException(new ProviderNotFoundException());
            $parameter = (new Link(key: 'bar', fromClass: 'App\\Resource\\Bar', extraProperties: ['throw_not_found' => $throws]))->setValue('missing');
            try {
                (new ReadLinkParameterProvider($locator, $factory))->provide($parameter, context: ['operation' => $target, 'request' => new Request()]);
                self::assertFalse($throws, 'Missing relation must throw by default');
                self::assertNull($parameter->getValue(null));
            } catch (NotFoundHttpException $exception) {
                self::assertTrue($throws);
                self::assertSame('Relation for link security not found.', $exception->getMessage());
            }
        }
    }
}
