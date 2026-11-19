import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path, PurePosixPath


VERSION = '2.4.0'
FILENAME = f'mongodb-{VERSION}.tgz'
URL = f'https://pecl.php.net/get/{FILENAME}'
MAX_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
PACKAGE_NAMESPACES = {
    '2.0': 'http://pear.php.net/dtd/package-2.0',
    '2.1': 'http://pear.php.net/dtd/package-2.1',
}


def validate_archive(path, expected_sha256=None):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError('Invalid MongoDB archive size or file type')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise ValueError('MongoDB archive SHA256 mismatch')
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        if sum(member.size for member in members) > MAX_EXPANDED_BYTES:
            raise ValueError('MongoDB archive exceeds expanded size limit')
        names = set()
        for member in members:
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or '..' in relative.parts or member.name in names:
                raise ValueError('Unsafe or duplicate MongoDB archive path')
            if not (member.isfile() or member.isdir()):
                raise ValueError('MongoDB archive contains a link or special file')
            names.add(member.name)
        metadata = archive.extractfile('package.xml').read()
        if b'<!DOCTYPE' in metadata or b'<!ENTITY' in metadata:
            raise ValueError('Unexpected XML entity in MongoDB package metadata')
        package = ElementTree.fromstring(metadata)
        namespace_uri = PACKAGE_NAMESPACES.get(package.get('version'))
        if namespace_uri is None or package.tag != f'{{{namespace_uri}}}package':
            raise ValueError('Unsupported or inconsistent PEAR package schema')
        namespace = {'pear': namespace_uri}
        if (package.findtext('pear:name', namespaces=namespace) != 'mongodb'
                or package.findtext('pear:channel', namespaces=namespace) != 'pecl.php.net'
                or package.findtext('pear:version/pear:release', namespaces=namespace) != VERSION):
            raise ValueError('MongoDB archive identity/version mismatch')
        verified = set()

        def verify_files(directory, parent):
            current = parent / directory.attrib.get('name', '').lstrip('/')
            for child in directory:
                kind = child.tag.rsplit('}', 1)[-1]
                if kind == 'dir':
                    verify_files(child, current)
                elif kind == 'file':
                    relative = current / child.attrib['name']
                    checksum = child.attrib.get('md5sum', '')
                    if '..' in relative.parts or relative.is_absolute() or not re.fullmatch('[0-9a-f]{32}', checksum):
                        raise ValueError('Invalid PECL file checksum/path')
                    name = f'mongodb-{VERSION}/{relative}'
                    payload = archive.extractfile(name).read()
                    if hashlib.md5(payload).hexdigest() != checksum:
                        raise ValueError('PECL file checksum mismatch: ' + name)
                    verified.add(name)

        for directory in package.findall('pear:contents/pear:dir', namespace):
            verify_files(directory, PurePosixPath())
        payloads = {member.name for member in members if member.isfile()} - {'package.xml'}
        if not verified or payloads != verified:
            raise ValueError('PECL file manifest does not cover archive payload')
    return digest


def prepare(cache, expected_sha256=None):
    if expected_sha256 and not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('Expected MongoDB SHA256 must be 64 lowercase hexadecimal characters')
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / FILENAME
    partial = cache / (FILENAME + '.part')
    receipt = cache / (FILENAME + '.json')
    receipt_temporary = cache / (FILENAME + '.json.tmp')
    for path in (archive, partial, receipt, receipt_temporary):
        if path.is_symlink():
            raise ValueError('Refusing symlink in dependency cache')
    if archive.exists():
        record = json.loads(receipt.read_text())
        if record['url'] != URL or record['version'] != VERSION or not re.fullmatch('[0-9a-f]{64}', record['sha256']):
            raise ValueError('Invalid MongoDB cache receipt')
        digest = validate_archive(archive, expected_sha256 or record['sha256'])
        if digest != record['sha256']:
            raise ValueError('MongoDB cache receipt mismatch')
        print('Verified cached MongoDB archive SHA256: ' + digest, file=sys.stderr)
        return archive
    if partial.exists() and partial.stat().st_size > MAX_BYTES:
        raise ValueError('Partial MongoDB archive exceeds size limit')
    for attempt in range(3):
        command = ['curl', '--fail', '--location', '--silent', '--show-error',
                   '--proto', '=https', '--proto-redir', '=https',
                   '--connect-timeout', '15', '--max-time', '60',
                   '--max-filesize', str(MAX_BYTES), '--continue-at', '-',
                   '--output', str(partial), URL]
        try:
            result = subprocess.run(command, timeout=65, check=False)
        except subprocess.TimeoutExpired:
            print('MongoDB transfer deadline reached; partial retained', file=sys.stderr)
            continue
        if result.returncode in (0, 33):
            try:
                digest = validate_archive(partial, expected_sha256)
            except (ValueError, KeyError, tarfile.TarError, EOFError, ElementTree.ParseError) as error:
                print(f'MongoDB archive validation attempt {attempt + 1}/3 failed: '
                      f'{type(error).__name__}: {error}', file=sys.stderr)
                partial.unlink(missing_ok=True)
                if result.returncode == 33:
                    print('MongoDB server refused Range; restarting within the attempt bound', file=sys.stderr)
                    continue
                if expected_sha256:
                    raise
                print('MongoDB downloaded payload was invalid; restarting without the partial', file=sys.stderr)
                continue
            record = dict(version=VERSION, url=URL, sha256=digest,
                          verification='HTTPS PECL origin, package identity and all package.xml file checksums',
                          digest_pinned=bool(expected_sha256))
            receipt_temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
            receipt_temporary.replace(receipt)
            partial.replace(archive)
            print('Verified downloaded MongoDB archive SHA256: ' + digest, file=sys.stderr)
            return archive
        print(f'MongoDB transfer attempt {attempt + 1}/3 failed ({result.returncode}); partial retained', file=sys.stderr)
    raise RuntimeError('MongoDB archive preparation exhausted its bounded attempts; see transfer/validation diagnostics')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    arguments = parser.parse_args()
    print(prepare(arguments.cache.resolve(), os.environ.get('TASK_MONGODB_ARCHIVE_SHA256')))
