import torch
from model import CharTokenizer, JarvisBrain

def test_tokenizer():
    text='JARVIS: electricidad, acción y ñ.'
    t=CharTokenizer(text)
    assert t.decode(t.encode(text))==text

def test_forward_backward():
    torch.manual_seed(4)
    t=CharTokenizer('prueba del cerebro local JARVIS')
    m=JarvisBrain(t.vocab_size,dim=32,heads=4,layers=2,context=32)
    x=torch.tensor([t.encode('prueba del cerebro local JARVIS')[:32]])
    logits,loss=m(x,x)
    assert logits.shape==(1,32,t.vocab_size)
    assert torch.isfinite(loss)
    loss.backward()
