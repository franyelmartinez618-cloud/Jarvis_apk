from __future__ import annotations
import collections,json,re
from pathlib import Path
ROOT=Path(__file__).parent; WEB=ROOT.parent/"web"
base=(ROOT/"corpus"/"es_base.txt").read_text(encoding="utf-8")
entries=[]
def add(title,text,source,kind="base",url=""):
    text=" ".join(str(text).split()).strip()
    if len(text)>=65: entries.append({"title":str(title)[:140],"text":text,"source":source,"kind":kind,"url":url})
def chunks(text,limit=520):
    current=[]; size=0
    for sentence in re.split(r"(?<=[.!?])\s+"," ".join(text.split())):
        if not sentence: continue
        if current and size+len(sentence)>limit:
            yield " ".join(current); current=[]; size=0
        current.append(sentence); size+=len(sentence)+1
    if current: yield " ".join(current)
for paragraph in base.splitlines():
    paragraph=paragraph.strip()
    if len(paragraph)<70 or paragraph.startswith("JARVIS — CORPUS"): continue
    for passage in chunks(paragraph):
        add(passage.split(".",1)[0][:100],passage,"Corpus original de JARVIS")
sources=ROOT/"corpus"/"wikipedia_sources.json"
if sources.exists():
    for row in json.loads(sources.read_text(encoding="utf-8")):
        for passage in chunks(row.get("extract","")):
            add(row.get("title","Wikipedia"),passage,"Wikipedia en español · CC BY-SA","wikipedia",row.get("url",""))
if not entries: raise SystemExit("Biblioteca de conocimiento vacía.")
freq=collections.Counter(re.findall(r"[a-záéíóúñü]{2,}"," ".join(e["title"]+" "+e["text"] for e in entries).lower()))
WEB.mkdir(parents=True,exist_ok=True)
(WEB/"knowledge.json").write_text(json.dumps({"version":1,"license":"Corpus original JARVIS y extractos Wikipedia atribuidos CC BY-SA.","lexicon":[w for w,_ in freq.most_common(6000)],"entries":entries},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
training=[]
for entry in entries:
    title=entry["title"].rstrip(".: ")
    training.append(f"\n\nJARVIS\nPregunta: ¿Qué sabes sobre {title}?\nRespuesta: {entry['text']}\n")
    training.append(f"\n\nJARVIS\nPregunta: Explica {title} de forma clara.\nRespuesta: {entry['text']}\n")
training.append("\n\n"+base)
(ROOT/"corpus"/"knowledge_train.txt").write_text("".join(training),encoding="utf-8")
print(f"Pasajes: {len(entries)}; caracteres de entrenamiento: {sum(map(len,training)):,}")
