"""Train JARVIS GPT from random initialization; requires an original corpus."""
import argparse,json,time
from pathlib import Path
import torch
from model import JarvisGPT
from tokenizer import ByteTokenizer
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--config",default="brain/config.json");ap.add_argument("--data",default="data/processed/corpus.txt");ap.add_argument("--out",default="checkpoints/jarvis.pt");args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text());text=Path(args.data).read_text(encoding="utf-8");tok=ByteTokenizer();ids=torch.tensor(tok.encode(text),dtype=torch.long)
    if len(ids)<cfg["context"]*4:raise SystemExit("Corpus demasiado pequeño: aporta más texto diverso antes de entrenar.")
    split=int(len(ids)*.98);train,val=ids[:split],ids[split:]
    if len(val)<cfg["context"]*2:raise SystemExit("La partición de validación es demasiado pequeña.")
    device="cuda" if torch.cuda.is_available() else "cpu";model=JarvisGPT(tok.vocab_size,cfg["context"],cfg["width"],cfg["layers"],cfg["heads"],cfg["dropout"]).to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=cfg["learning_rate"],weight_decay=.1);scaler=torch.amp.GradScaler("cuda",enabled=device=="cuda")
    def batch(src):
        ix=torch.randint(0,len(src)-cfg["context"]-1,(cfg["batch_size"],));x=torch.stack([src[i:i+cfg["context"]] for i in ix]).to(device);y=torch.stack([src[i+1:i+cfg["context"]+1] for i in ix]).to(device);return x,y
    @torch.no_grad()
    def evaluate():
        model.eval();values=[]
        for _ in range(20):
            x,y=batch(val);_,loss=model(x,y);values.append(loss.item())
        model.train();return sum(values)/len(values)
    best=float("inf");started=time.time()
    for step in range(1,cfg["steps"]+1):
        x,y=batch(train);opt.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda",dtype=torch.float16,enabled=device=="cuda"):_,loss=model(x,y)
        scaler.scale(loss).backward();scaler.unscale_(opt);torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);scaler.step(opt);scaler.update()
        if step%cfg["log_every"]==0:
            vl=evaluate();print(f"step {step}/{cfg['steps']} train={loss.item():.4f} val={vl:.4f} elapsed={time.time()-started:.0f}s",flush=True)
            if vl<best:
                best=vl;out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);torch.save({"model":model.state_dict(),"config":cfg,"step":step,"val_loss":best,"tokenizer":"jarvis-byte-v1"},out)
    print(f"Entrenamiento terminado. Mejor val_loss={best:.4f}. Checkpoint: {args.out}")
if __name__=="__main__":main()
