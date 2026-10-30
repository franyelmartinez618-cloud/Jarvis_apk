from pathlib import Path
import argparse,random,time,torch
from model import CharTokenizer,JarvisBrain,export_web
def main():
 p=argparse.ArgumentParser();p.add_argument("--corpus",type=Path,default=Path(__file__).parent/"corpus");p.add_argument("--steps",type=int,default=3000);p.add_argument("--batch",type=int,default=8);p.add_argument("--context",type=int,default=96);p.add_argument("--dim",type=int,default=48);p.add_argument("--layers",type=int,default=2);p.add_argument("--heads",type=int,default=4);p.add_argument("--output",type=Path,default=Path(__file__).parents[1]/"web"/"brain.json");a=p.parse_args()
 if not 100<=a.steps<=500000 or a.dim%a.heads:raise SystemExit("Invalid training settings")
 files=sorted(a.corpus.rglob("*.txt"))
 if not files:raise SystemExit("No JARVIS corpus found")
 text="\n\n".join(f.read_text(encoding="utf-8",errors="replace") for f in files)
 if len(text)<1200:raise SystemExit("Training corpus too small")
 random.seed(20261030);torch.manual_seed(20261030);torch.set_num_threads(max(1,min(4,torch.get_num_threads())))
 tok=CharTokenizer(text);ids=torch.tensor(tok.encode(text,True,True),dtype=torch.long)
 model=JarvisBrain(tok.vocab_size,a.dim,a.heads,a.layers,a.context);opt=torch.optim.AdamW(model.parameters(),lr=4e-4,weight_decay=.05)
 start=time.time();model.train()
 for step in range(1,a.steps+1):
  starts=torch.randint(0,len(ids)-a.context-1,(a.batch,))
  x=torch.stack([ids[s:s+a.context] for s in starts]);y=torch.stack([ids[s+1:s+a.context+1] for s in starts])
  _,loss=model(x,y);opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step()
  if step%max(1,a.steps//10)==0:print(f"step={step}/{a.steps} loss={loss.item():.4f} elapsed={time.time()-start:.1f}s",flush=True)
 export_web(model,tok,a.output);print(f"Exported {a.output}; params={sum(p.numel() for p in model.parameters()):,}")
if __name__=="__main__":main()
