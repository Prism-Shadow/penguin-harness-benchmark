<?php
declare(strict_types=1);
$root = getenv('REPO_DIR') ?: '/workspace';
$autoload = $root . '/vendor/autoload.php';
if (!is_file($autoload)) { throw new RuntimeException('Composer autoload is unavailable'); }
require $autoload;

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

function expect_feature(bool $condition, string $message): void {
    if (!$condition) { throw new RuntimeException($message); }
}

class FeatureRequest extends Request {
    protected Method $method = Method::GET;
    public function resolveEndpoint(): string { return '/feature'; }
}
class FeatureConnector extends Connector {
    public function resolveBaseUrl(): string { return 'https://feature.test'; }
}
class FixtureTestSender extends GuzzleSender {
    protected function createGuzzleClient(): GuzzleHttp\Client {
        $handler = new GuzzleHttp\Handler\MockHandler([
            new GuzzleHttp\Psr7\Response(200, ['content-type' => 'application/json'], '{"fixture":true}'),
        ]);
        $this->handlerStack = GuzzleHttp\HandlerStack::create($handler);
        return new GuzzleHttp\Client(['handler' => $this->handlerStack, 'http_errors' => false]);
    }
}
class FixtureConnector extends FeatureConnector {
    protected string $defaultSender = FixtureTestSender::class;
}
class BodyConnector extends FeatureConnector implements Saloon\Contracts\Body\HasBody {
    public function body(): JsonBodyRepository { return new JsonBodyRepository(['connector' => true]); }
}
class OAuthConnector extends FeatureConnector {
    use Saloon\Traits\OAuth2\AuthorizationCodeGrant;
    protected function defaultOauthConfig(): Saloon\Helpers\OAuth2\OAuthConfig {
        return Saloon\Helpers\OAuth2\OAuthConfig::make()->setClientId('client')->setClientSecret('secret')->setRedirectUri('https://client.test/callback');
    }
}
class MissingMethodRequest extends Request {
    public function resolveEndpoint(): string { return '/missing'; }
}
function send_feature_mock(?MockClient $mock = null, ?Request $request = null): Response {
    return (new FeatureConnector)->send($request ?? new FeatureRequest, $mock ?? new MockClient([new MockResponse(['ok' => true], 200)]));
}

class NonGuzzleProbeSender implements Saloon\Contracts\Sender {
    public static int $sent = 0;
    public function getFactoryCollection(): Saloon\Data\FactoryCollection {
        return (new GuzzleSender)->getFactoryCollection();
    }
    public function send(Saloon\Contracts\PendingRequest $pendingRequest): Response {
        self::$sent++;
        return Response::fromPsrResponse(new GuzzleHttp\Psr7\Response(202, [], '{}'), $pendingRequest, $pendingRequest->createPsrRequest());
    }
    public function sendAsync(Saloon\Contracts\PendingRequest $pendingRequest): GuzzleHttp\Promise\PromiseInterface {
        return GuzzleHttp\Promise\Create::promiseFor($this->send($pendingRequest));
    }
}
class NonGuzzleProbeConnector extends FeatureConnector {
    protected string $defaultSender = NonGuzzleProbeSender::class;
}
