"""Train the first-party JARVIS Transformer from random initialization."""
import argparse
import json
import time
from pathlib import Path

import torch

from model import JarvisGPT
from tokenizer import ByteTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="brain/config.json")
    parser.add_argument("--data", default="data/processed/corpus.txt")
    parser.add_argument("--out", default="checkpoints/jarvis.pt")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    corpus = Path(args.data).read_text(encoding="utf-8")
    tokenizer = ByteTokenizer()
    token_ids = torch.tensor(tokenizer.encode(corpus), dtype=torch.long)
    context = int(config["context"])
    if len(token_ids) < context * 6:
        raise SystemExit(
            f"Corpus insuficiente: {len(token_ids)} bytes; se requieren al menos {context * 6}. "
            "Añade material diverso y autorizado."
        )

    # Keep a contiguous holdout so validation is never used to update gradients.
    split = int(len(token_ids) * 0.90)
    train_ids, validation_ids = token_ids[:split], token_ids[split:]
    if len(validation_ids) < context * 2:
        raise SystemExit("La partición de validación es demasiado pequeña.")

    seed = int(config.get("seed", 20261030))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

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
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    batch_size = int(config["batch_size"])

    def make_batch(source):
        max_start = len(source) - context - 1
        starts = torch.randint(0, max_start + 1, (batch_size,))
        inputs = torch.stack([source[i:i + context] for i in starts]).to(device)
        targets = torch.stack([source[i + 1:i + context + 1] for i in starts]).to(device)
        return inputs, targets

    @torch.no_grad()
    def evaluate():
        model.eval()
        measurements = []
        for _ in range(12):
            inputs, targets = make_batch(validation_ids)
            _, loss = model(inputs, targets)
            measurements.append(float(loss.item()))
        model.train()
        return sum(measurements) / len(measurements)

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    best_validation = float("inf")
    steps_without_improvement = 0
    patience = int(config.get("patience", 8))
    log_every = int(config["log_every"])
    total_steps = int(config["steps"])
    started = time.time()

    for step in range(1, total_steps + 1):
        inputs, targets = make_batch(train_ids)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
            _, loss = model(inputs, targets)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()

        if step % log_every != 0 and step != total_steps:
            continue

        validation_loss = evaluate()
        elapsed = time.time() - started
        print(
            f"step {step}/{total_steps} train={loss.item():.4f} "
            f"validation={validation_loss:.4f} elapsed={elapsed:.0f}s",
            flush=True,
        )
        if validation_loss < best_validation:
            best_validation = validation_loss
            steps_without_improvement = 0
            torch.save(
                {
                    "model": model.state_dict(),
                    "config": config,
                    "step": step,
                    "val_loss": best_validation,
                    "tokenizer": "jarvis-byte-v1",
                    "training_seed": seed,
                    "training_source": str(Path(args.data)),
                },
                output,
            )
        else:
            steps_without_improvement += 1
            if steps_without_improvement >= patience:
                print(f"Early stopping: validación sin mejora durante {patience} evaluaciones.")
                break

    if not output.is_file():
        raise SystemExit("No se creó un checkpoint; revisa el corpus y la configuración.")
    print(
        f"Entrenamiento finalizado. Mejor validation_loss={best_validation:.4f}. "
        f"Checkpoint: {output}"
    )


if __name__ == "__main__":
    main()
