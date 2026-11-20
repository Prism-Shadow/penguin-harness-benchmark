<?php

declare(strict_types=1);

require_once __DIR__.'/StandaloneFilterFixture.php';

final class LegacyFiltersTest extends PHPUnit\Framework\TestCase
{
    use StandaloneFilterFixture;

    public function testRegistryInjectedFiltersKeepExistingBehavior(): void
    {
        $manager = $this->datedManager();
        $registry = $this->registryFor($manager);
        $date = new ApiPlatform\Doctrine\Orm\Filter\DateFilter($registry, properties: ['created' => 'include_null_before']);
        self::assertSame([1, 2, 4], $this->filterIds($manager, $date, ['created' => ['before' => '2026-01-02']]));
        self::assertArrayHasKey('created[before]', $date->getDescription(TaskDatedRecord::class));
        $exists = new ApiPlatform\Doctrine\Orm\Filter\ExistsFilter($registry, properties: ['note' => null]);
        self::assertSame([3, 4], $this->filterIds($manager, $exists, ['exists' => ['note' => false]]));
        self::assertSame([1, 2, 3, 4], $this->filterIds($manager, $exists, ['exists' => ['note' => 'invalid']]));
    }
}
