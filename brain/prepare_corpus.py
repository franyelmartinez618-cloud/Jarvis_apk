"""Build a deduplicated, provenance-audited text corpus for JARVIS."""
import argparse
import hashlib
import json
import re
from pathlib import Path

EXTS = {".txt", ".md", ".jsonl"}
TRAINING_LICENSES = {
    "CC0-1.0", "Public-Domain", "CC-BY-4.0", "Owner-Created", "Permission-Granted"
}


def iter_text(path):
    if path.suffix.lower() in {".txt", ".md"}:
        yield path.read_text(encoding="utf-8", errors="replace")
    elif path.suffix.lower() == ".jsonl":
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
                value = item.get("text", "")
                if isinstance(value, str) and value.strip():
                    yield value
            except json.JSONDecodeError:
                continue


def load_registry(source: Path):
    if source.as_posix().endswith("data/seed") or source.name == "seed":
        return None
    registry_path = source / "SOURCES.json"
    if not registry_path.is_file():
        raise SystemExit(
            f"Falta {registry_path}. Cada fuente externa debe declarar licencia y permiso "
            "de entrenamiento en SOURCES.json."
        )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = registry.get("sources", [])
    if not isinstance(entries, list):
        raise SystemExit("SOURCES.json debe contener una lista 'sources'.")
    return entries


def provenance_for(path: Path, source: Path, registry):
    if registry is None:
        return {
            "source": "JARVIS project-authored seed corpus",
            "url": "",
            "license": "Owner-Created",
            "training_allowed": True,
            "commercial_use": True,
            "attribution": "Contenido original redactado para el proyecto JARVIS.",
        }
    relative = path.relative_to(source).as_posix()
    entry = next((item for item in registry if item.get("file") == relative), None)
    if entry is None:
        raise SystemExit(f"La fuente {relative} no tiene registro en SOURCES.json.")
    license_name = entry.get("license")
    if license_name not in TRAINING_LICENSES:
        raise SystemExit(f"Licencia no aprobada para {relative}: {license_name!r}.")
    if entry.get("training_allowed") is not True or entry.get("commercial_use") is not True:
        raise SystemExit(f"La fuente {relative} no autoriza entrenamiento y uso comercial.")
    if license_name in {"CC-BY-4.0", "Permission-Granted"} and not entry.get("attribution"):
        raise SystemExit(f"La fuente {relative} requiere atribución documentada.")
    if license_name == "Permission-Granted" and not entry.get("permission_evidence"):
        raise SystemExit(f"La fuente {relative} requiere enlace o evidencia de permiso.")
    if license_name == "Public-Domain" and not entry.get("public_domain_basis"):
        raise SystemExit(f"La fuente {relative} requiere justificar dominio público.")
    return {
        "source": entry.get("source", ""),
        "url": entry.get("url", ""),
        "license": license_name,
        "training_allowed": True,
        "commercial_use": True,
        "attribution": entry.get("attribution", ""),
        "permission_evidence": entry.get("permission_evidence", ""),
        "public_domain_basis": entry.get("public_domain_basis", ""),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw")
    parser.add_argument("--output", default="data/processed/corpus.txt")
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    registry = load_registry(source) if source.exists() else []
    seen = set()
    rows = []
    manifest = []
    for path in sorted(p for p in source.rglob("*") if p.is_file()) if source.exists() else []:
        if path.name == "SOURCES.json" or path.suffix.lower() not in EXTS:
            continue
        provenance = provenance_for(path, source, registry)
        for text in iter_text(path):
            clean = re.sub(r"\n{3,}", "\n\n", text.replace("\x00", " ")).strip()
            digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
            if len(clean) < 40 or digest in seen:
                continue
            seen.add(digest)
            rows.append(clean)
            manifest.append({
                "file": path.relative_to(source).as_posix(),
                "sha256": digest,
                "characters": len(clean),
                **provenance,
            })
    if not rows:
        raise SystemExit("No hay textos válidos. Añade fuentes .txt, .md o .jsonl autorizadas.")
    output.write_text("\n\n<|document|>\n\n".join(rows), encoding="utf-8")
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"{len(rows)} documentos · {sum(map(len, rows)):,} caracteres · "
        f"{len({row['license'] for row in manifest})} licencias · {output}"
    )


if __name__ == "__main__":
    main()
