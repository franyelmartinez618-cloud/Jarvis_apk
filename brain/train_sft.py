"""Supervised instruction tuning for the first-party JARVIS Transformer."""
import argparse
import json
import math
import random
import re
import time
from pathlib import Path

import torch

from model import JarvisGPT
from tokenizer import BOS, EOS, PAD, ByteTokenizer

PAIR = re.compile(r"### Usuario:\s*(.*?)\s*### JARVIS:\s*(.*)", re.DOTALL)
PROMPT_PREFIXES = (
    "Explícalo con claridad: ",
    "Necesito entender esto: ",
    "Dame una respuesta directa: ",
    "Ayúdame con esta duda: ",
    "Responde de forma breve y precisa: ",
)


def augment_training_prompts(examples):
    """Create varied user phrasings without leaking variants into validation."""
    expanded = []
    for example in examples:
        question, answer, source = example[:3]
        metadata = tuple(example[3:])
        expanded.append((question, answer, source, *metadata))
        expanded.extend((prefix + question, answer, source, *metadata) for prefix in PROMPT_PREFIXES)
    return expanded


def load_pairs(root: Path, include_generated: bool = False):
    examples = []
    for path in sorted(root.rglob("*.jsonl")):
        if not include_generated and path.name == "zz_generated_curriculum.jsonl":
            continue
        for line_index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = record.get("text", "")
            if not isinstance(text, str):
                continue
            match = PAIR.search(text)
            if not match:
                continue
            question, answer = match.group(1).strip(), match.group(2).strip()
            if question and answer:
                group_id = str(record.get("group_id") or f"{path.as_posix()}:{line_index}")
                examples.append((question, answer, str(path), group_id))
    if len(examples) < 10:
        raise SystemExit(f"Se necesitan al menos 10 pares instrucción-respuesta; encontrados {len(examples)}.")
    return examples


def encode_pair(question, answer, tokenizer, context):
    prompt = f"### Usuario:\n{question}\n### JARVIS:\n"
    prompt_ids = tokenizer.encode(prompt)
    answer_ids = tokenizer.encode(answer)
    # Preserve the answer and the end marker; trim old prompt bytes first.
    answer_ids = answer_ids[: max(1, context - 8)]
    prompt_budget = max(1, context - len(answer_ids) - 1)
    prompt_ids = prompt_ids[-prompt_budget:]
    ids = [BOS] + prompt_ids + answer_ids + [EOS]
    answer_start = 1 + len(prompt_ids)
    inputs = ids[:-1]
    targets = ids[1:]
    mask_before = answer_start - 1
    targets[:mask_before] = [-100] * mask_before
    if len(inputs) > context:
        inputs = inputs[-context:]
        targets = targets[-context:]
    padding = context - len(inputs)
    inputs += [PAD] * padding
    targets += [-100] * padding
    return inputs, targets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--data", default="data/seed")
    parser.add_argument("--extra-data", action="append", default=[])
    parser.add_argument("--config", default="brain/sft-config.json")
    parser.add_argument("--out", default="checkpoints/jarvis-sft.pt")
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="Include synthetic arithmetic examples in SFT (excluded by default).",
    )
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    pretrained = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if pretrained.get("tokenizer") != "jarvis-byte-v1":
        raise SystemExit("El checkpoint base no usa el tokenizador propio de JARVIS.")
    model_config = pretrained["config"]
    context = int(model_config["context"])
    tokenizer = ByteTokenizer()
    raw_examples = load_pairs(Path(args.data), include_generated=args.include_generated)
    for extra_root in args.extra_data:
        raw_examples.extend(load_pairs(Path(extra_root), include_generated=args.include_generated))
    random.Random(int(config.get("seed", 20261030))).shuffle(raw_examples)
    group_ids = list(dict.fromkeys(example[3] for example in raw_examples))
    random.Random(int(config.get("seed", 20261030))).shuffle(group_ids)
    validation_group_count = max(1, round(len(group_ids) * 0.10))
    validation_groups = set(group_ids[:validation_group_count])
    validation_raw = [example for example in raw_examples if example[3] in validation_groups]
    train_raw = [example for example in raw_examples if example[3] not in validation_groups]
    if not train_raw or not validation_raw:
        raise SystemExit("La división por conversación dejó un conjunto vacío.")
    base_train_count = len(train_raw)
    train_raw = augment_training_prompts(train_raw)
    train_examples = [encode_pair(q, a, tokenizer, context) for q, a, *_ in train_raw]
    validation_examples = [encode_pair(q, a, tokenizer, context) for q, a, *_ in validation_raw]

    seed = int(config.get("seed", 20261030))
    random.seed(seed)
    torch.manual_seed(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    use_bf16 = device == "cuda" and torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if use_bf16 else torch.float16
    model = JarvisGPT(
        tokenizer.vocab_size, context, int(model_config["width"]),
        int(model_config["layers"]), int(model_config["heads"]),
        float(model_config["dropout"]),
    ).to(device)
    model.load_state_dict(pretrained["model"])
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["learning_rate"]),
        weight_decay=float(config.get("weight_decay", 0.01)),
        betas=(0.9, 0.95),
    )
    batch_size = int(config["batch_size"])
    accumulation = max(1, int(config.get("gradient_accumulation", 1)))
    steps = int(config["steps"])
    warmup = int(config.get("warmup_steps", max(1, steps // 20)))
    min_lr = float(config.get("min_learning_rate", config["learning_rate"] * 0.1))
    log_every = int(config.get("log_every", 100))
    max_eval_batches = max(1, int(config.get("max_eval_batches", 64)))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    last_output = output.with_name(output.stem + "-last" + output.suffix)
    best_loss = float("inf")
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda" and not use_bf16)

    def batch(examples):
        selected = random.choices(examples, k=batch_size)
        x = torch.tensor([item[0] for item in selected], dtype=torch.long, device=device)
        y = torch.tensor([item[1] for item in selected], dtype=torch.long, device=device)
        return x, y

    @torch.no_grad()
    def evaluate():
        model.eval()
        losses = []
        eval_steps = min(max_eval_batches, max(1, math.ceil(len(validation_examples) / batch_size)))
        for _ in range(eval_steps):
            x, y = batch(validation_examples)
            with torch.autocast("cuda", dtype=dtype, enabled=device == "cuda"):
                _, loss = model(x, y)
            losses.append(float(loss.item()))
        model.train()
        return sum(losses) / len(losses)

    parameter_count = sum(p.numel() for p in model.parameters())
    print(
        f"JARVIS SFT | device={device} | params={parameter_count:,} | "
        f"train_pairs={len(train_examples)} (from {base_train_count} authored pairs) | "
        f"validation_pairs={len(validation_examples)} | conversation_groups={len(group_ids)} | "
        f"extra_sources={len(args.extra_data)} | synthetic_examples={'included' if args.include_generated else 'excluded'}",
        flush=True,
    )
    started = time.time()
    optimizer.zero_grad(set_to_none=True)
    for step in range(1, steps + 1):
        if step <= warmup:
            lr = float(config["learning_rate"]) * step / max(1, warmup)
        else:
            progress = min(1.0, (step - warmup) / max(1, steps - warmup))
            lr = min_lr + (float(config["learning_rate"]) - min_lr) * 0.5 * (1 + math.cos(math.pi * progress))
        for group in optimizer.param_groups:
            group["lr"] = lr

        total_loss = 0.0
        for _ in range(accumulation):
            x, y = batch(train_examples)
            autocast = torch.autocast("cuda", dtype=dtype) if device == "cuda" else torch.autocast("cpu", enabled=False)
            with autocast:
                _, loss = model(x, y)
                loss = loss / accumulation
            scaler.scale(loss).backward()
            total_loss += float(loss.detach().item())
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)

        if step % log_every and step != steps:
            continue
        val_loss = evaluate()
        record = {
            "step": step,
            "train_loss": total_loss,
            "validation_loss": val_loss,
            "validation_perplexity": math.exp(min(20.0, val_loss)),
            "learning_rate": lr,
            "elapsed_seconds": round(time.time() - started, 1),
        }
        print(json.dumps(record), flush=True)
        state = {
            "model": model.state_dict(),
            "config": model_config,
            "step": step,
            "val_loss": val_loss,
            "tokenizer": "jarvis-byte-v1",
            "stage": "supervised-instruction-tuning",
            "training_seed": seed,
            "source_checkpoint": str(args.checkpoint),
            "training_examples": len(train_examples),
            "training_conversation_groups": len(group_ids) - validation_group_count,
            "validation_conversation_groups": validation_group_count,
        }
        torch.save(state, last_output)
        if val_loss < best_loss:
            best_loss = val_loss
            torch.save(state, output)

    if not output.is_file():
        raise SystemExit("No se generó el checkpoint SFT.")
    print(f"SFT completado; best_validation_loss={best_loss:.6f}; checkpoint={output}", flush=True)


if __name__ == "__main__":
    main()
