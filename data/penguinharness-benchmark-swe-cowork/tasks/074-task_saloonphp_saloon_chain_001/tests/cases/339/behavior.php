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


$response = send_feature_mock(new MockClient([new MockResponse(['ok' => true], 200)]));
expect_feature($response->successful() === true, 'successful response semantics changed');

echo 'behavior 339 passed', PHP_EOL;
