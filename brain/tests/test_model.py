import unittest
import torch

from model import JarvisGPT


class TransformerTests(unittest.TestCase):
    def test_forward_shape_and_loss(self):
        model = JarvisGPT(vocab_size=260, context=16, width=32, layers=2, heads=4, dropout=0.0)
        inputs = torch.randint(0, 260, (2, 12))
        logits, loss = model(inputs, inputs)
        self.assertEqual(tuple(logits.shape), (2, 12, 260))
        self.assertTrue(torch.isfinite(loss).item())

    def test_future_tokens_do_not_change_previous_logits(self):
        torch.manual_seed(7)
        model = JarvisGPT(vocab_size=260, context=16, width=32, layers=2, heads=4, dropout=0.0)
        model.eval()
        first = torch.randint(0, 260, (1, 10))
        second = first.clone()
        second[:, 8] = (second[:, 8] + 1) % 260
        with torch.no_grad():
            logits_a, _ = model(first)
            logits_b, _ = model(second)
        self.assertTrue(torch.allclose(logits_a[:, :8], logits_b[:, :8], atol=1e-6, rtol=1e-6))


if __name__ == "__main__":
    unittest.main()
