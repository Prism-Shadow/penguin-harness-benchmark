<?php
declare(strict_types=1);
require __DIR__ . '/../../support/bootstrap.php';
use Saloon\Enums\Method;
use Saloon\Http\Request;
use Saloon\Http\Connector;
use Saloon\Http\Response;
use Saloon\Http\Faking\Fixture;
use Saloon\Http\Faking\MockClient;
use Saloon\Http\Faking\MockResponse;
use Saloon\Http\Senders\GuzzleSender;
use Saloon\Helpers\Storage;
use Saloon\Repositories\Body\ArrayBodyRepository;
use Saloon\Repositories\Body\StringBodyRepository;
use Saloon\Repositories\Body\JsonBodyRepository;
use Saloon\Repositories\Body\MultipartBodyRepository;
use Saloon\Data\MultipartValue;


$events = [];
$connector = new FeatureConnector;
$connector->middleware()->onRequest(function () use (&$events): void { $events[] = 'request'; });
$connector->middleware()->onResponse(function (Response $response) use (&$events): void {
    expect_feature($response->json('ok') === true, 'middleware saw an undecoded response');
    $events[] = 'response';
});
$response = $connector->send(new FeatureRequest, new MockClient([new MockResponse(['ok' => true], 200)]));
expect_feature($events === ['request', 'response'], 'middleware callbacks ran in the wrong order');
expect_feature($response->json('ok') === true, 'middleware changed response decoding');

echo 'behavior 296 passed', PHP_EOL;
