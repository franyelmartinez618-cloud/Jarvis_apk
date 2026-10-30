"""Deterministic UTF-8 byte tokenizer: IDs 0..255 are raw bytes."""
BOS,EOS,PAD,VOCAB_SIZE=256,257,258,259
class ByteTokenizer:
    vocab_size=VOCAB_SIZE
    def encode(self,text,add_bos=False,add_eos=False):
        ids=list(text.encode("utf-8"))
        if add_bos:ids.insert(0,BOS)
        if add_eos:ids.append(EOS)
        return ids
    def decode(self,ids):
        return bytes(i for i in ids if 0<=int(i)<256).decode("utf-8",errors="replace")
