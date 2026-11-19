<?php
declare(strict_types=1);

$repo = getenv('REPO_DIR') ?: dirname(__DIR__, 2);
require $repo . '/vendor/autoload.php';

function behavior_assert(bool $condition, string $message): void
{
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$validator = Symfony\Component\Validator\Validation::createValidatorBuilder()->enableAnnotationMapping()->getValidator();
$value = str_repeat('x', 65536);
$violations = $validator->validatePropertyValue(App\Entity\CustomerMeta::class, 'value', $value);
behavior_assert(count($violations) > 0, 'oversized meta value was accepted');
