<?php

declare(strict_types=1);
require_once __DIR__.'/StandaloneFilterFixture.php';

trait LiteralSearchFixture
{
    use StandaloneFilterFixture;

    private function literalSearchIds(object $filter, mixed $value): array
    {
        $manager = $this->datedManager();
        foreach (['50%_\\done', 'head50%_\\done', 'head 50%_\\done tail', '50XXdone'] as $i => $note) {
            $manager->find(TaskDatedRecord::class, $i + 1)->note = $note;
        }
        $manager->flush();
        $builder = $manager->createQueryBuilder()->select('r')->from(TaskDatedRecord::class, 'r')->orderBy('r.id');
        $parameter = (new ApiPlatform\Metadata\QueryParameter(key: 'q', property: 'note'))->setValue($value);
        $filter->apply($builder, new ApiPlatform\Doctrine\Orm\Util\QueryNameGenerator(), TaskDatedRecord::class, context: ['parameter' => $parameter]);
        return array_map(static fn ($r) => $r->id, $builder->getQuery()->getResult());
    }
}
