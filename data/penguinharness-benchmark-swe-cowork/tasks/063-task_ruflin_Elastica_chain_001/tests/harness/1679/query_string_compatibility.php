<?php
declare(strict_types=1);
require __DIR__ . '/../bootstrap.php';

$query = new \Elastica\Query();
foreach (['setFrom' => 'from', 'setSize' => 'size'] as $setter => $parameter) {
    foreach ([0, 17, 203] as $value) {
        checkx($query === $query->$setter($value), $setter . ' is not fluent');
        checkx($value === $query->getParam($parameter), $parameter . ' integer was not retained');
        checkx($value === arrayish($query->toArray())[$parameter], $parameter . ' did not serialize');
    }
    foreach (['20', 20.5, true, null] as $invalid) {
        expect_type_error(static function () use ($query, $setter, $invalid): void {
            $query->$setter($invalid);
        }, $setter . ' accepted a non-integer');
        checkx(203 === $query->getParam($parameter), 'rejected input changed pagination state');
    }
}
checkx($query === $query->setSize(), 'default size setter is not fluent');
checkx(10 === $query->getParam('size'), 'default size must remain 10');
