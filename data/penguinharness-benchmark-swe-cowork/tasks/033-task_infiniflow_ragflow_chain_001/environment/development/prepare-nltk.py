import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

def prepare_data(source, destination):
    for record in json.loads((source / 'nltk-data-sources.json').read_text()):
        archive = source / (record['name'] + '.zip')
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == record['sha256']
        target = destination / record['category']
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                path = PurePosixPath(member.filename)
                assert not path.is_absolute() and '..' not in path.parts
                assert path.parts[0] == record['name']
            package.extractall(target)


def main():
    prepare_data(Path('/opt/ragflow-development-inputs'), Path('/opt/ragflow-nltk-data'))
    import nltk
    assert nltk.data.find('tokenizers/punkt_tab')
    assert nltk.data.find('corpora/wordnet')
    print('Offline NLTK data ready:', nltk.__version__)


if __name__ == '__main__':
    main()
