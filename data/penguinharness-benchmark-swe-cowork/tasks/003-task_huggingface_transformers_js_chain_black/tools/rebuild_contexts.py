"""Check/generate the current workplace contract projection."""
import argparse
import json
import tomllib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def serialized(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    revision=tomllib.loads((ROOT/'task.toml').read_text())['metadata']['task_version']
    public=(ROOT/'environment/public_contracts.md').read_text()
    corpus=ROOT/'environment/workplace-service/original/authoring/corpus'
    path=corpus/'docs.json';docs=json.loads(path.read_text())
    doc=next(d for d in docs if d['key']=='DOC-RUNTIME-CONTRACTS')
    doc['versions']=[{'version':revision,'body':public,'state':'current','change_summary':'Current callable interfaces and lifecycle contracts'}]
    outputs={path:serialized(docs)}
    for target,content in outputs.items():
        if args.check:
            if target.read_text()!=content:raise SystemExit('stale workplace projection: '+str(target))
        else:target.write_text(content)

if __name__=='__main__':main()
