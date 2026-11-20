<?php

declare(strict_types=1);

use Doctrine\DBAL\DriverManager;
use Doctrine\ORM\EntityManager;
use Doctrine\ORM\Mapping as ORM;
use Doctrine\ORM\ORMSetup;
use Doctrine\ORM\Tools\SchemaTool;
use Doctrine\Persistence\ManagerRegistry;

#[ORM\Entity]
class TaskDatedRecord
{
    public function __construct(
        #[ORM\Id, ORM\Column(type: 'integer')] public int $id,
        #[ORM\Column(type: 'datetime_immutable', nullable: true)] public ?DateTimeImmutable $created,
        #[ORM\Column(nullable: true)] public ?string $note,
    ) {}
}

trait StandaloneFilterFixture
{
    private function datedManager(): EntityManager
    {
        $config = ORMSetup::createAttributeMetadataConfiguration([], true);
        $config->enableNativeLazyObjects(true);
        $manager = new EntityManager(DriverManager::getConnection(['driver' => 'pdo_sqlite', 'memory' => true]), $config);
        (new SchemaTool($manager))->createSchema([$manager->getClassMetadata(TaskDatedRecord::class)]);
        foreach ([['2026-01-01', 'old'], ['2026-01-02', ''], ['2026-01-03', null], [null, null]] as $i => [$date, $note]) {
            $manager->persist(new TaskDatedRecord($i + 1, $date ? new DateTimeImmutable($date) : null, $note));
        }
        $manager->flush();
        return $manager;
    }

    private function filterIds(EntityManager $manager, object $filter, array $filters): array
    {
        $builder = $manager->createQueryBuilder()->select('r')->from(TaskDatedRecord::class, 'r')->orderBy('r.id');
        $filter->apply($builder, new ApiPlatform\Doctrine\Orm\Util\QueryNameGenerator(), TaskDatedRecord::class, context: ['filters' => $filters]);
        return array_map(static fn ($record) => $record->id, $builder->getQuery()->getResult());
    }

    private function registryFor(object $manager): ManagerRegistry
    {
        $registry = $this->createStub(ManagerRegistry::class);
        $registry->method('getManagerForClass')->willReturn($manager);
        return $registry;
    }
}
