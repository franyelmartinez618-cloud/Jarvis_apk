import unittest
from tokenizer import ByteTokenizer, BOS, EOS, VOCAB_SIZE
class TokenizerTests(unittest.TestCase):
    def test_round_trip_unicode(self):
        source="JARVIS — señor, ¿cómo estás? British English."
        tok=ByteTokenizer()
        self.assertEqual(tok.decode(tok.encode(source)),source)
    def test_special_tokens_are_outside_byte_range(self):
        tok=ByteTokenizer()
        self.assertEqual(tok.encode("A",add_bos=True,add_eos=True),[BOS,65,EOS])
        self.assertEqual(tok.vocab_size,VOCAB_SIZE)
if __name__=="__main__":unittest.main()
