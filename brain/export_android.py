"""Export a JARVIS-owned PyTorch checkpoint to the first-party Android runtime format."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import torch

MAGIC = b"JARVIS01"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default="checkpoints/jarvis.pt")
    parser.add_argument("--output", default="brain/artifacts/jarvis-brain.bin")
    args = parser.parse_args()

    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.is_file():
        raise SystemExit(f"No existe el checkpoint propio: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if checkpoint.get("tokenizer") != "jarvis-byte-v1":
        raise SystemExit("El checkpoint no usa el tokenizador byte-level oficial de JARVIS.")
    config = checkpoint.get("config") or {}
    vocab = 260
    context = int(config["context"])
    width = int(config["width"])
    layers = int(config["layers"])
    heads = int(config["heads"])
    if width % heads:
        raise SystemExit("width debe ser divisible por heads.")

    state = checkpoint["model"]
    tensors = ["token.weight", "position.weight"]
    for index in range(layers):
        prefix = f"blocks.{index}."
        tensors.extend([
            prefix + "n1.weight", prefix + "n1.bias",
            prefix + "attn.qkv.weight", prefix + "attn.proj.weight",
            prefix + "n2.weight", prefix + "n2.bias",
            prefix + "mlp.0.weight", prefix + "mlp.0.bias",
            prefix + "mlp.2.weight", prefix + "mlp.2.bias",
        ])
    tensors.extend(["norm.weight", "norm.bias"])

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(MAGIC)
        stream.write(struct.pack("<5i", vocab, context, width, layers, heads))
        for key in tensors:
            if key not in state:
                raise SystemExit(f"Falta el tensor requerido: {key}")
            tensor = state[key].detach().to(device="cpu", dtype=torch.float32).contiguous()
            stream.write(tensor.numpy().astype("<f4", copy=False).tobytes(order="C"))
    temporary.replace(output)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    metadata = {
        "format": "JARVIS01",
        "architecture": "first-party-causal-transformer",
        "tokenizer": checkpoint["tokenizer"],
        "vocab_size": vocab,
        "context": context,
        "width": width,
        "layers": layers,
        "heads": heads,
        "training_step": int(checkpoint.get("step", 0)),
        "validation_loss": float(checkpoint.get("val_loss", 0.0)),
        "sha256": digest,
        "source_checkpoint": str(checkpoint_path),
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Checkpoint JARVIS exportado: {output}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
