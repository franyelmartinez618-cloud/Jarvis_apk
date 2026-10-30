"""Evaluate an experimental JARVIS checkpoint on held-out prompts."""
import argparse
import json
from pathlib import Path

import torch

from model import JarvisGPT
from tokenizer import BOS, EOS, PAD, ByteTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--questions", default="brain/eval/questions.jsonl")
    parser.add_argument("--output", default="reports/jarvis-quality.json")
    parser.add_argument("--max-tokens", type=int, default=180)
    args = parser.parse_args()

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    config = checkpoint["config"]
    tokenizer = ByteTokenizer()
    model = JarvisGPT(
        tokenizer.vocab_size, config["context"], config["width"],
        config["layers"], config["heads"], config["dropout"],
    )
    model.load_state_dict(checkpoint["model"])
    model.eval()
    questions = [
        json.loads(line)
        for line in Path(args.questions).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = []
    for item in questions:
        prompt = f"### Usuario:\n{item['question']}\n### JARVIS:\n"
        ids = [BOS] + tokenizer.encode(prompt)
        generated = []
        with torch.no_grad():
            for _ in range(args.max_tokens):
                context_ids = torch.tensor([ids[-config["context"]:]], dtype=torch.long)
                logits, _ = model(context_ids)
                next_token = int(logits[0, -1].argmax().item())
                if next_token in {BOS, EOS, PAD}:
                    break
                generated.append(next_token)
                ids.append(next_token)
        answer = tokenizer.decode(generated).strip()
        normalized = answer.casefold()
        terms = item.get("must_include", [])
        found = [term for term in terms if term.casefold() in normalized]
        keyword_recall = len(found) / max(1, len(terms))
        trigrams = [answer[i:i + 3] for i in range(max(0, len(answer) - 2))]
        repeated = 1.0 - (len(set(trigrams)) / max(1, len(trigrams)))
        results.append({
            "question": item["question"],
            "answer": answer,
            "must_include": terms,
            "matched": found,
            "keyword_recall": keyword_recall,
            "repeated_trigram_ratio": repeated,
            "generated_bytes": len(answer.encode("utf-8")),
        })

    nonempty = sum(bool(item["answer"]) for item in results) / max(1, len(results))
    avg_recall = sum(item["keyword_recall"] for item in results) / max(1, len(results))
    avg_repetition = sum(item["repeated_trigram_ratio"] for item in results) / max(1, len(results))
    quality_passed = nonempty >= 0.90 and avg_recall >= 0.25 and avg_repetition <= 0.35
    report = {
        "checkpoint": str(args.checkpoint),
        "training_stage": checkpoint.get("stage", "pretraining"),
        "step": checkpoint.get("step", 0),
        "validation_loss": checkpoint.get("val_loss"),
        "question_count": len(results),
        "nonempty_rate": nonempty,
        "average_keyword_recall": avg_recall,
        "average_repeated_trigram_ratio": avg_repetition,
        "quality_passed": quality_passed,
        "warning": "Heuristic smoke test only; passing does not establish factuality or general intelligence.",
        "results": results,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False))
    if not quality_passed:
        print("CHECKPOINT RECHAZADO: no se integra automáticamente en la APK.")


if __name__ == "__main__":
    main()
