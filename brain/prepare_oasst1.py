"""Prepare human-only Spanish OASST1 pairs and record their Apache-2.0 provenance."""
import argparse
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path

SOURCE_URL = "https://huggingface.co/datasets/OpenAssistant/oasst1"
DATA_URL = SOURCE_URL + "/resolve/main/2023-04-12_oasst_ready.messages.jsonl.gz"


def approved_human_message(item):
    if item.get("lang") != "es":
        return False
    if item.get("role") not in {"prompter", "assistant"}:
        return False
    if item.get("deleted") is not False or item.get("review_result") is not True:
        return False
    # Strictly exclude synthetic responses and every record attributed to a model.
    if item.get("synthetic") is not False:
        return False
    if item.get("model_name") not in (None, ""):
        return False
    text = item.get("text")
    if not isinstance(text, str) or len(text.strip()) < 12 or len(text) > 6000:
        return False
    labels = item.get("labels") or {}
    for name in ("pii", "spam", "hate_speech", "sexual_content", "not_appropriate"):
        label = labels.get(name) or {}
        if int(label.get("count", 0) or 0) > 0 and float(label.get("value", 0.0) or 0.0) > 0.0:
            return False
    toxicity = labels.get("toxicity") or {}
    if int(toxicity.get("count", 0) or 0) > 0 and float(toxicity.get("value", 0.0) or 0.0) >= 0.5:
        return False
    return True


def clean_text(value):
    return re.sub(r"\s+", " ", value.replace("\x00", " ")).strip()


def build_pairs(messages):
    by_id = {item.get("message_id"): item for item in messages if item.get("message_id")}
    candidates = defaultdict(list)
    for assistant in messages:
        if not approved_human_message(assistant) or assistant.get("role") != "assistant":
            continue
        parent = by_id.get(assistant.get("parent_id"))
        if not parent or not approved_human_message(parent) or parent.get("role") != "prompter":
            continue
        question, answer = clean_text(parent["text"]), clean_text(assistant["text"])
        if len(question) < 12 or len(answer) < 20:
            continue
        group_id = assistant.get("message_tree_id") or parent.get("message_tree_id")
        if not group_id:
            continue
        rank = assistant.get("rank")
        rank = int(rank) if isinstance(rank, int) else 999999
        review_count = int(assistant.get("review_count") or 0)
        candidates[parent["message_id"]].append((rank, -review_count, str(assistant.get("message_id")), group_id, question, answer))

    pairs = []
    seen = set()
    for parent_id in sorted(candidates):
        # Keep one highest-ranked human answer per prompt to avoid sibling duplicates.
        _, _, _, group_id, question, answer = min(candidates[parent_id])
        key = (question.casefold(), answer.casefold())
        if key in seen:
            continue
        seen.add(key)
        pairs.append({
            "text": f"### Usuario:\n{question}\n### JARVIS:\n{answer}",
            "group_id": str(group_id),
            "origin": "OpenAssistant OASST1 human-reviewed Spanish conversation",
        })
    return pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Compressed OASST1 messages JSONL.")
    parser.add_argument("--output", default="data/raw/oasst_es_human.jsonl")
    parser.add_argument("--license-file", default="data/raw/OASST-LICENSE")
    parser.add_argument("--registry", default="data/raw/SOURCES.json")
    parser.add_argument("--min-pairs", type=int, default=500)
    args = parser.parse_args()

    source_file = Path(args.input)
    license_file = Path(args.license_file)
    output = Path(args.output)
    registry_path = Path(args.registry)
    if not source_file.is_file() or not license_file.is_file():
        raise SystemExit("Falta el archivo OASST1 o su licencia Apache-2.0.")
    license_text = license_file.read_text(encoding="utf-8", errors="replace")
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        raise SystemExit("El archivo de licencia descargado no parece Apache License 2.0.")

    messages = []
    with gzip.open(source_file, "rt", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                messages.append(item)
    pairs = build_pairs(messages)
    if len(pairs) < args.min_pairs:
        raise SystemExit(
            f"Solo se prepararon {len(pairs)} pares humanos en español; "
            f"se requieren al menos {args.min_pairs}."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for item in pairs:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")

    registry = {
        "sources": [{
            "file": output.name,
            "source": "OpenAssistant contributors — OASST1, Spanish human-reviewed non-synthetic pairs",
            "url": SOURCE_URL,
            "license": "Apache-2.0",
            "training_allowed": True,
            "commercial_use": True,
            "attribution": "OpenAssistant contributors, OpenAssistant Conversations Dataset (OASST1), Apache License 2.0.",
            "permission_evidence": "Official OASST1 dataset card declares Apache-2.0; synthetic/model-attributed messages excluded.",
            "license_text_file": license_file.name,
        }]
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"OASST1 filtrado: {len(messages):,} mensajes revisados · "
        f"{len(pairs):,} pares humanos en español · sin respuestas sintéticas/modeladas."
    )


if __name__ == "__main__":
    main()
