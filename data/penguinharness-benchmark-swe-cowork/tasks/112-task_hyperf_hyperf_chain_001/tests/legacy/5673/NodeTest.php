<?php

declare(strict_types=1);

use Hyperf\Support\Filesystem\Filesystem;
use PHPUnit\Framework\TestCase;

final class NodeTest extends TestCase
{
    public function testSupportFilesystemPerformsWriteAtomicReplaceReadAndDelete(): void
    {
        $filesystem = new Filesystem();
        $directory = sys_get_temp_dir() . '/hyperf-node-5673-' . bin2hex(random_bytes(5));
        mkdir($directory);
        $path = $directory . '/state.txt';

        try {
            self::assertSame(5, $filesystem->put($path, 'first'));
            self::assertSame('first', $filesystem->get($path));
            $filesystem->replace($path, 'second');
            self::assertSame('second', $filesystem->get($path));
            self::assertTrue($filesystem->delete($path));
            self::assertFalse($filesystem->exists($path));
        } finally {
            if (is_file($path)) {
                unlink($path);
            }
            if (is_dir($directory)) {
                rmdir($directory);
            }
        }
    }
}
