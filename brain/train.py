"""Train JARVIS's first-party causal Transformer from random initialization.

Training data is split by document before any token windows are sampled. Checkpoints
are resumable and retain optimizer state; validation documents never enter gradients.
"""
import argparse
import json
import math
import random
import time
from contextlib import nullcontext
from pathlib import Path

import torch

from model import JarvisGPT
from tokenizer import ByteTokenizer

DOCUMENT_SEPARATOR = "\\n\\n<|document|>\\n\\n"


def split_documents(corpus: str, seed: int):
    documents = [part.strip() for part in corpus.split("<|document|>") if part.strip()]
    if len(documents) < 2:
        raise SystemExit(
            "El corpus debe contener al menos dos documentos independientes separados "
            "por <|document|>; no se permite validar sobre fragmentos del mismo documento."
        )
    random.Random(seed).shuffle(documents)
    validation_count = max(1, round(len(documents) * 0.10))
    validation_docs = documents[:validation_count]
    train_docs = documents[validation_count:]
    if not train_docs:
        raise SystemExit("No hay documentos suficientes para entrenamiento.")
    return train_docs, validation_docs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="brain/config.json")
    parser.add_argument("--data", default="data/processed/corpus.txt")
    parser.add_argument("--out", default="checkpoints/jarvis.pt")
    parser.add_argument("--resume", default="")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    corpus = Path(args.data).read_text(encoding="utf-8")
    seed = int(config.get("seed", 20261030))
    train_docs, validation_docs = split_documents(corpus, seed)
    tokenizer = ByteTokenizer()

    train_text = DOCUMENT_SEPARATOR.join(train_docs)
    validation_text = DOCUMENT_SEPARATOR.join(validation_docs)
    train_ids = torch.tensor(tokenizer.encode(train_text), dtype=torch.long)
    validation_ids = torch.tensor(tokenizer.encode(validation_text), dtype=torch.long)
    context = int(config["context"])
    if len(train_ids) < int(config.get("minimum_train_bytes", context * 4)) or len(validation_ids) < int(config.get("minimum_validation_bytes", context * 2)):
        raise SystemExit(
            f"Corpus insuficiente para contexto {context}: "
            f"train={len(train_ids):,} bytes, validation={len(validation_ids):,} bytes."
        )

    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    device = "cuda" if torch.cuda.is_available() else "cpu"
    use_bf16 = device == "cuda" and bool(config.get("bf16", True)) and torch.cuda.is_bf16_supported()
    use_fp16 = device == "cuda" and not use_bf16
    amp_dtype = torch.bfloat16 if use_bf16 else torch.float16

    model = JarvisGPT(
        tokenizer.vocab_size,
        context,
        int(config["width"]),
        int(config["layers"]),
        int(config["heads"]),
        float(config["dropout"]),
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["learning_rate"]),
        weight_decay=float(config.get("weight_decay", 0.1)),
        betas=tuple(config.get("betas", [0.9, 0.95])),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=use_fp16)
    batch_size = int(config["batch_size"])
    accumulation = max(1, int(config.get("gradient_accumulation", 1)))
    total_steps = int(config["steps"])
    warmup_steps = int(config.get("warmup_steps", max(1, total_steps // 20)))
    min_lr = float(config.get("min_learning_rate", config["learning_rate"] * 0.1))
    log_every = int(config.get("log_every", 250))
    eval_batches = int(config.get("eval_batches", 24))
    patience = int(config.get("patience", 0))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    last_output = output.with_name(output.stem + "-last" + output.suffix)
    metrics_path = output.with_suffix(".metrics.jsonl")

    start_step = 0
    best_validation = float("inf")
    steps_without_improvement = 0
    tokens_seen = 0
    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=False)
        if checkpoint.get("tokenizer") != "jarvis-byte-v1":
            raise SystemExit("El checkpoint de reanudación usa otro tokenizador.")
        model.load_state_dict(checkpoint["model"])
        if "optimizer" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer"])
        start_step = int(checkpoint.get("step", 0))
        best_validation = float(checkpoint.get("val_loss", float("inf")))
        tokens_seen = int(checkpoint.get("tokens_seen", 0))
        print(f"Reanudando desde paso {start_step:,}; tokens vistos={tokens_seen:,}")

    def learning_rate(step):
        if step <= warmup_steps:
            return float(config["learning_rate"]) * step / max(1, warmup_steps)
        progress = min(1.0, (step - warmup_steps) / max(1, total_steps - warmup_steps))
        cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
        return min_lr + (float(config["learning_rate"]) - min_lr) * cosine

    def make_batch(source):
        max_start = len(source) - context - 1
        starts = torch.randint(0, max_start + 1, (batch_size,))
        inputs = torch.stack([source[i:i + context] for i in starts]).to(device, non_blocking=True)
        targets = torch.stack([source[i + 1:i + context + 1] for i in starts]).to(device, non_blocking=True)
        return inputs, targets

    @torch.no_grad()
    def evaluate():
        model.eval()
        measurements = []
        for _ in range(eval_batches):
            inputs, targets = make_batch(validation_ids)
            autocast = (
                torch.autocast(device_type="cuda", dtype=amp_dtype)
                if device == "cuda" else nullcontext()
            )
            with autocast:
                _, loss = model(inputs, targets)
            measurements.append(float(loss.item()))
        model.train()
        return sum(measurements) / len(measurements)

    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    print(
        f"JARVIS desde cero | device={device} | params={parameter_count:,} | "
        f"train_docs={len(train_docs)} | val_docs={len(validation_docs)} | "
        f"train_bytes={len(train_ids):,} | val_bytes={len(validation_ids):,} | "
        f"context={context} | batch={batch_size}x{accumulation} | "
        f"precision={'bf16' if use_bf16 else 'fp16' if use_fp16 else 'fp32'}",
        flush=True,
    )
    started = time.time()
    optimizer.zero_grad(set_to_none=True)

    for step in range(start_step + 1, total_steps + 1):
        lr = learning_rate(step)
        for group in optimizer.param_groups:
            group["lr"] = lr

        accumulated_loss = 0.0
        for _ in range(accumulation):
            inputs, targets = make_batch(train_ids)
            autocast = (
                torch.autocast(device_type="cuda", dtype=amp_dtype)
                if device == "cuda" else nullcontext()
            )
            with autocast:
                _, loss = model(inputs, targets)
                scaled_loss = loss / accumulation
            scaler.scale(scaled_loss).backward()
            accumulated_loss += float(loss.detach().item())
            tokens_seen += batch_size * context

        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), float(config.get("grad_clip", 1.0)))
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)

        if step % log_every != 0 and step != total_steps:
            continue

        validation_loss = evaluate()
        elapsed = time.time() - started
        train_loss = accumulated_loss / accumulation
        record = {
            "step": step,
            "train_loss": train_loss,
            "validation_loss": validation_loss,
            "validation_perplexity": math.exp(min(20.0, validation_loss)),
            "learning_rate": lr,
            "tokens_seen": tokens_seen,
            "elapsed_seconds": round(elapsed, 1),
            "device": device,
        }
        print(json.dumps(record, ensure_ascii=False), flush=True)
        with metrics_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\\n")

        state = {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "config": config,
            "step": step,
            "val_loss": validation_loss,
            "tokenizer": "jarvis-byte-v1",
            "training_seed": seed,
            "training_source": str(Path(args.data)),
            "tokens_seen": tokens_seen,
        }
        torch.save(state, last_output)
        if validation_loss < best_validation:
            best_validation = validation_loss
            steps_without_improvement = 0
            torch.save(state, output)
        else:
            steps_without_improvement += 1
            if patience and steps_without_improvement >= patience:
                print(f"Early stopping: {patience} evaluaciones sin mejora.", flush=True)
                break

    if not output.is_file():
        raise SystemExit("No se creó el checkpoint óptimo; revisa el corpus y la configuración.")
    print(
        f"Entrenamiento terminado. best_validation_loss={best_validation:.6f}; "
        f"tokens_seen={tokens_seen:,}; best={output}; last={last_output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
