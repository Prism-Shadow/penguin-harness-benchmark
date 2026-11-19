<?php
declare(strict_types=1);

function source_table(PDO $source, string $table, array $rows, array $columns = []): void
{
    $columns = $rows ? array_keys($rows[0]) : $columns;
    if (!$columns) {
        $columns = ['id'];
    }
    $source->exec('CREATE TABLE "' . $table . '" (' . implode(', ', array_map(fn($column) => '"' . $column . '"', $columns)) . ')');
    if ($rows) {
        $insert = $source->prepare('INSERT INTO "' . $table . '" VALUES (' . implode(', ', array_fill(0, count($columns), '?')) . ')');
        foreach ($rows as $row) {
            $insert->execute(array_values($row));
        }
    }
}

function source_instance(PDO $source, string $prefix, string $marker, int $count): void
{
    source_table($source, $prefix . 'configuration', [['option' => 'version', 'value' => '1.3.0'], ['option' => 'revision', 'value' => '1400']]);
    source_table($source, $prefix . 'users', [['userID' => 1, 'name' => $marker, 'mail' => $marker . '@example.com', 'alias' => $marker, 'active' => 1, 'trash' => 0, 'ban' => 0, 'globalRoleID' => 2]]);
    source_table($source, $prefix . 'customers', [[
        'customerID' => 1, 'name' => $marker, 'visible' => 1, 'trash' => 0, 'timezone' => 'UTC',
        'comment' => '', 'company' => '', 'fax' => '', 'homepage' => '', 'mobile' => '', 'mail' => '',
        'phone' => '', 'contact' => '', 'street' => '', 'zipcode' => '', 'city' => '',
    ]]);
    source_table($source, $prefix . 'projects', [['projectID' => 1, 'customerID' => 1, 'name' => $marker, 'comment' => '', 'visible' => 1, 'trash' => 0, 'budget' => 0]]);
    source_table($source, $prefix . 'activities', [['activityID' => 1, 'name' => $marker, 'visible' => 1, 'trash' => 0, 'comment' => '', 'budget' => 0]]);
    source_table($source, $prefix . 'projects_activities', [['projectID' => 1, 'activityID' => 1]]);
    source_table($source, $prefix . 'preferences', [], ['userID', 'option', 'value']);
    foreach (['fixedRates', 'rates', 'groups', 'groups_users', 'groups_customers', 'groups_projects', 'groups_activities'] as $table) {
        source_table($source, $prefix . $table, []);
    }
    $entries = [];
    for ($index = 0; $index < $count; $index++) {
        $entries[] = [
            'timeEntryID' => $index + 1, 'userID' => 1, 'projectID' => 1, 'activityID' => 1,
            'start' => 1577836800 + 3600 * $index, 'end' => 1577836800 + 3600 * $index + 1800,
            'description' => $marker, 'comment' => '', 'rate' => 10, 'fixedRate' => 0,
            'cleared' => 0, 'location' => '', 'trackingNumber' => '',
        ];
    }
    source_table($source, $prefix . 'timeSheet', $entries, ['timeEntryID']);
}
