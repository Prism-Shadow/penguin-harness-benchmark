<?php

declare(strict_types=1);

use Hyperf\Support\Composer;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testSupportComposerSurvivesWhileRetiredUtilsApiRaisesError(): void
    {
        self::assertSame('hyperf/hyperf', Composer::getJsonContent()->get('name'));

        $raised = null;
        try {
            Hyperf\Utils\Composer::getJsonContent();
        } catch (Error $error) {
            $raised = $error;
        }

        self::assertInstanceOf(Error::class, $raised);
        self::assertStringContainsString('Hyperf\\Utils\\Composer', $raised->getMessage());

        $rootManifest = json_decode(
            (string) file_get_contents(BASE_PATH . '/composer.json'),
            true,
            512,
            JSON_THROW_ON_ERROR
        );
        self::assertNotContains('src/utils/src/Functions.php', $rootManifest['autoload']['files'] ?? []);
    }
}
