import argparse,torch
from pathlib import Path
from model import JarvisGPT
from tokenizer import ByteTokenizer
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--checkpoint",required=True);ap.add_argument("--prompt",required=True);ap.add_argument("--tokens",type=int,default=300);args=ap.parse_args()
    ck=torch.load(args.checkpoint,map_location="cpu",weights_only=False);c=ck["config"];tok=ByteTokenizer()
    model=JarvisGPT(tok.vocab_size,c["context"],c["width"],c["layers"],c["heads"],c["dropout"]);model.load_state_dict(ck["model"]);model.eval();ids=torch.tensor([tok.encode(args.prompt)],dtype=torch.long)
    for _ in range(args.tokens):
        logits,_=model(ids[:,-c["context"]:]);probs=torch.softmax(logits[:,-1,:]/.9,dim=-1);nxt=torch.multinomial(probs,1);ids=torch.cat([ids,nxt],dim=1)
    print(tok.decode(ids[0].tolist()))
if __name__=="__main__":main()
