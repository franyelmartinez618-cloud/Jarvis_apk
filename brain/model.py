"""JARVIS causal Transformer. Parameters are initialized randomly; no pretrained model is loaded."""
from __future__ import annotations
import json, math
from pathlib import Path
import torch
from torch import nn
from torch.nn import functional as F
class CharTokenizer:
    def __init__(self,text):
        self.vocab=["<UNK>","<BOS>","<EOS>"]+sorted(set(text)); self.stoi={c:i for i,c in enumerate(self.vocab)}
        self.unk,self.bos,self.eos=0,1,2
    def encode(self,text,bos=False,eos=False):
        ids=[self.stoi.get(c,0) for c in text]
        if bos: ids.insert(0,1)
        if eos: ids.append(2)
        return ids
    def decode(self,ids): return "".join(self.vocab[i] for i in ids if 3<=i<len(self.vocab))
    @property
    def vocab_size(self): return len(self.vocab)
class Attention(nn.Module):
    def __init__(self,dim,heads,context):
        super().__init__()
        if dim%heads: raise ValueError("dim must divide heads")
        self.heads=heads; self.hdim=dim//heads
        self.qkv=nn.Linear(dim,3*dim); self.proj=nn.Linear(dim,dim)
        self.register_buffer("mask",torch.tril(torch.ones(context,context,dtype=torch.bool))[None,None],persistent=False)
    def forward(self,x):
        b,t,c=x.shape; q,k,v=self.qkv(x).split(c,dim=-1)
        def reshape(z): return z.view(b,t,self.heads,self.hdim).transpose(1,2)
        q,k,v=reshape(q),reshape(k),reshape(v)
        scores=(q@k.transpose(-2,-1))/math.sqrt(self.hdim)
        scores=scores.masked_fill(~self.mask[:,:,:t,:t],float("-inf"))
        return self.proj((scores.softmax(-1)@v).transpose(1,2).contiguous().view(b,t,c))
class Block(nn.Module):
    def __init__(self,dim,heads,context):
        super().__init__()
        self.ln1=nn.LayerNorm(dim); self.attn=Attention(dim,heads,context)
        self.ln2=nn.LayerNorm(dim); self.fc1=nn.Linear(dim,4*dim); self.fc2=nn.Linear(4*dim,dim)
    def forward(self,x):
        x=x+self.attn(self.ln1(x))
        return x+self.fc2(F.gelu(self.fc1(self.ln2(x))))
class JarvisBrain(nn.Module):
    def __init__(self,vocab,dim=48,heads=4,layers=2,context=96):
        super().__init__()
        self.config={"vocab":vocab,"dim":dim,"heads":heads,"layers":layers,"context":context,"format":"jarvis-from-zero-v1"}
        self.token=nn.Embedding(vocab,dim); self.position=nn.Embedding(context,dim)
        self.blocks=nn.ModuleList([Block(dim,heads,context) for _ in range(layers)])
        self.norm=nn.LayerNorm(dim); self.head=nn.Linear(dim,vocab,bias=False); self.head.weight=self.token.weight
        self.apply(self.initialize)
    @staticmethod
    def initialize(layer):
        if isinstance(layer,nn.Linear):
            nn.init.normal_(layer.weight,0,.02)
            if layer.bias is not None: nn.init.zeros_(layer.bias)
        elif isinstance(layer,nn.Embedding): nn.init.normal_(layer.weight,0,.02)
    def forward(self,ids,targets=None):
        b,t=ids.shape
        if t>self.config["context"]:
            ids=ids[:,-self.config["context"]:]
            if targets is not None: targets=targets[:,-self.config["context"]:]
            t=ids.shape[1]
        pos=torch.arange(t,device=ids.device); x=self.token(ids)+self.position(pos)[None,:,:]
        for block in self.blocks: x=block(x)
        logits=self.head(self.norm(x))
        loss=None if targets is None else F.cross_entropy(logits.reshape(-1,logits.size(-1)),targets.reshape(-1))
        return logits,loss
    @torch.no_grad()
    def generate(self,prompt,steps=120):
        self.eval(); output=list(prompt); device=next(self.parameters()).device
        for _ in range(steps):
            x=torch.tensor([output[-self.config["context"]:]],dtype=torch.long,device=device)
            logits,_=self(x); next_id=int(torch.multinomial(logits[0,-1].softmax(-1),1).item())
            if next_id==2: break
            output.append(next_id)
        return output
def export_web(model,tokenizer,path:Path):
    weights={k:v.detach().cpu().float().contiguous().view(-1).tolist() for k,v in model.state_dict().items()}
    payload={"format":"jarvis-from-zero-v1","config":model.config,"vocab":tokenizer.vocab,"weights":weights}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
