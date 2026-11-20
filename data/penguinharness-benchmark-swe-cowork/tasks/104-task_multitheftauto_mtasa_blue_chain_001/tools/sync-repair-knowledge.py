#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def render(root):
    contract = json.loads((root / "repair-contracts.json").read_text())
    authoring = root / "environment/workplace-service/original/authoring"
    docs = json.loads((authoring / "corpus/docs.json").read_text())
    packs = {path: json.loads(path.read_text()) for path in sorted((authoring / "orgchat_auto1/knowledge_packs").glob("*.json"))}
    revision = contract["revision"]
    for entry in contract["contracts"]:
        doc = next(doc for doc in docs if doc["key"] == entry["doc"])
        marker = revision + ": API contract " + entry["card_id"]
        if not any(version.get("change_summary") == marker for version in doc["versions"]):
            doc["versions"].append({
                "version": max(version["version"] for version in doc["versions"]) + 1,
                "at": "2026-09-20T00:00:00+08:00", "author_id": entry["owner"],
                "change_summary": marker, "state": "published", "reviewer_ids": [],
                "body": doc["versions"][-1]["body"] + "\n\n## " + revision + " 可行动接口契约\n\n以下补充优先于旧版的待查措辞；不是历史上已经披露过的事实。\n\n" + entry["answer"] + "\n",
            })
        pack = next(pack for pack in packs.values() if pack["owner"] == entry["owner"])
        fact = next((fact for fact in pack["facts"] if fact["card_id"] == entry["card_id"]), None)
        if fact is None:
            fact = {key: entry[key] for key in ("iu", "card_id", "topic", "module")}
            fact["keywords"] = [entry["card_id"], entry["topic"], "GetModelSpecialAbilityModel", "SetModelSpecialAbilityModel"]
            fact["disclosure"] = {"strategy": "one_consumer_path", "minimum_user_turns": 1, "one_topic_at_a_time": True, "clarification_prompts": [], "answer_prefix": "修订接口契约："}
            pack["facts"].append(fact)
        fact["answer"] = entry["answer"]
        if entry["answer"] not in max(doc["versions"], key=lambda version: version["version"])["body"]:
            raise ValueError("Public contract is stale; bump the contract revision: " + entry["card_id"])
    outputs = {authoring / "corpus/docs.json": json.dumps(docs, ensure_ascii=False, indent=2) + "\n"}
    outputs.update({path: json.dumps(pack, ensure_ascii=False, indent=2) + "\n" for path, pack in packs.items()})
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for path, text in render(root).items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit("Out of sync: " + str(path.relative_to(root)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    print("Knowledge and public documents synchronized")


if __name__ == "__main__":
    main()
