from pathlib import Path
import argparse,json,torch
from model import CharTokenizer,JarvisBrain
def main():
 p=argparse.ArgumentParser();p.add_argument("--model",type=Path,default=Path("web/brain.json"));a=p.parse_args()
 data=json.loads(a.model.read_text(encoding="utf-8"));tok=object.__new__(CharTokenizer);tok.vocab=data["vocab"];tok.stoi={c:i for i,c in enumerate(tok.vocab)}
 c=data["config"];model=JarvisBrain(c["vocab"],c["dim"],c["heads"],c["layers"],c["context"])
 state={k:torch.tensor(v).reshape(model.state_dict()[k].shape) for k,v in data["weights"].items()};model.load_state_dict(state)
 prompts=["¿Qué es la electricidad?","Explica la fotosíntesis.","¿Cómo funciona Internet?","¿Qué es una base de datos?"];samples=[]
 for prompt in prompts:
  raw=tok.decode(model.generate(tok.encode("JARVIS\nPregunta: "+prompt+"\nRespuesta:"),140))
  answer=raw.split("Respuesta:",1)[-1].split("\n\n",1)[0].strip()
  tokens=[w.lower().strip(".,;:!?¿¡") for w in answer.split() if len(w)>1]
  common=set("el la de que y en es un una los las por para con se como del al datos".split())
  ratio=sum(w in common for w in tokens)/max(1,len(tokens))
  passed=len(tokens)>=8 and len(answer)>45 and ratio>.08
  samples.append({"prompt":prompt,"answer":answer,"common_word_ratio":round(ratio,3),"passes":passed})
 report={"pass":all(x["passes"] for x in samples),"samples":samples,"note":"Prueba mínima; no demuestra inteligencia general."}
 print(json.dumps(report,ensure_ascii=False,indent=2))
 (a.model.parent/"evaluation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
