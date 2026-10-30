"""Prepare an auditable corpus from user-provided text files."""
import argparse,hashlib,json,re
from pathlib import Path
EXTS={".txt",".md"}
def iter_text(path):
    if path.suffix.lower() in EXTS:yield path.read_text(encoding="utf-8",errors="replace")
    elif path.suffix.lower()==".jsonl":
        for line in path.read_text(encoding="utf-8",errors="replace").splitlines():
            try:
                item=json.loads(line);value=item.get("text","")
                if isinstance(value,str) and value.strip():yield value
            except json.JSONDecodeError:continue
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input",default="data/raw");ap.add_argument("--output",default="data/processed/corpus.txt");args=ap.parse_args()
    source=Path(args.input);out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);seen=set();rows=[];manifest=[]
    for path in sorted(p for p in source.rglob("*") if p.is_file()) if source.exists() else []:
        for text in iter_text(path):
            clean=re.sub(r"\n{3,}","\n\n",text.replace("\x00"," ")).strip();digest=hashlib.sha256(clean.encode()).hexdigest()
            if len(clean)<40 or digest in seen:continue
            seen.add(digest);rows.append(clean);manifest.append({"file":str(path),"sha256":digest,"characters":len(clean)})
    if not rows:raise SystemExit("No hay textos válidos. Añade archivos .txt, .md o .jsonl con campo text.")
    out.write_text("\n\n<|document|>\n\n".join(rows),encoding="utf-8")
    out.with_suffix(".manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"{len(rows)} documentos · {sum(map(len,rows)):,} caracteres · {out}")
if __name__=="__main__":main()
