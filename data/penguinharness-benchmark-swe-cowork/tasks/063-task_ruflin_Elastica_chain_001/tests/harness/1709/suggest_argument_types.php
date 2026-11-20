<?php
declare(strict_types=1);
require __DIR__ . '/../bootstrap.php';

$suggest = new \Elastica\QueryBuilder\DSL\Suggest();
$factories = [
    'term' => \Elastica\Suggest\Term::class,
    'phrase' => \Elastica\Suggest\Phrase::class,
    'completion' => \Elastica\Suggest\Completion::class,
];
foreach ($factories as $factory => $expectedClass) {
    foreach ([['catalog', 'title'], ['lookup', 'description.raw']] as $case) {
        [$name, $field] = $case;
        $result = $suggest->$factory($name, $field);
        checkx($result instanceof $expectedClass, $factory . ' returned the wrong type');
        checkx($name === $result->getName(), $factory . ' lost the caller name');
        checkx($field === $result->getParam('field'), $factory . ' lost the caller field');
        checkx($field === arrayish($result->toArray())[$factory]['field'], $factory . ' field did not serialize');
    }
    foreach ([123, false, 1.5, null] as $invalid) {
        expect_type_error(static function () use ($suggest, $factory, $invalid): void {
            $suggest->$factory($invalid, 'title');
        }, $factory . ' accepted a non-string name');
        expect_type_error(static function () use ($suggest, $factory, $invalid): void {
            $suggest->$factory('catalog', $invalid);
        }, $factory . ' accepted a non-string field');
    }
}
