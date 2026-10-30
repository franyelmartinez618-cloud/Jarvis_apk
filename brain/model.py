"""Tiny GPT-style decoder implemented for JARVIS; no pretrained weights."""
import torch
from torch import nn
from torch.nn import functional as F
class CausalAttention(nn.Module):
    def __init__(self,width,heads,dropout):
        super().__init__()
        if width%heads: raise ValueError("width must be divisible by heads")
        self.heads,self.head_dim=heads,width//heads
        self.qkv=nn.Linear(width,3*width,bias=False);self.proj=nn.Linear(width,width,bias=False);self.dropout=nn.Dropout(dropout)
    def forward(self,x):
        b,t,c=x.shape;q,k,v=self.qkv(x).chunk(3,dim=-1)
        def split(z):return z.view(b,t,self.heads,self.head_dim).transpose(1,2)
        q,k,v=split(q),split(k),split(v)
        y=F.scaled_dot_product_attention(q,k,v,is_causal=True,dropout_p=self.dropout.p if self.training else 0.0)
        return self.dropout(self.proj(y.transpose(1,2).contiguous().view(b,t,c)))
class Block(nn.Module):
    def __init__(self,width,heads,dropout):
        super().__init__();self.n1=nn.LayerNorm(width);self.n2=nn.LayerNorm(width);self.attn=CausalAttention(width,heads,dropout)
        self.mlp=nn.Sequential(nn.Linear(width,4*width),nn.GELU(),nn.Linear(4*width,width),nn.Dropout(dropout))
    def forward(self,x):return x+self.attn(self.n1(x))+self.mlp(self.n2(x))
class JarvisGPT(nn.Module):
    def __init__(self,vocab_size=260,context=512,width=256,layers=6,heads=8,dropout=.1):
        super().__init__();self.context=context;self.token=nn.Embedding(vocab_size,width);self.position=nn.Embedding(context,width)
        self.blocks=nn.Sequential(*[Block(width,heads,dropout) for _ in range(layers)]);self.norm=nn.LayerNorm(width);self.lm_head=nn.Linear(width,vocab_size,bias=False);self.lm_head.weight=self.token.weight
        self.apply(self._init)
    @staticmethod
    def _init(m):
        if isinstance(m,nn.Linear):
            nn.init.normal_(m.weight,mean=0.0,std=.02)
            if m.bias is not None:nn.init.zeros_(m.bias)
        elif isinstance(m,nn.Embedding):nn.init.normal_(m.weight,mean=0.0,std=.02)
    def forward(self,ids,targets=None):
        b,t=ids.shape
        if t>self.context:raise ValueError(f"sequence {t} exceeds context {self.context}")
        pos=torch.arange(t,device=ids.device);x=self.blocks(self.token(ids)+self.position(pos)[None,:,:]);logits=self.lm_head(self.norm(x))
        loss=F.cross_entropy(logits.reshape(-1,logits.size(-1)),targets.reshape(-1)) if targets is not None else None
        return logits,loss
