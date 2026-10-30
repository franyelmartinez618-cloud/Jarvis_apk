import unittest
import torch

from evaluate import apply_repetition_penalty, sample_next_token


class GenerationTests(unittest.TestCase):
    def test_repetition_penalty_reduces_recent_token_scores(self):
        logits = torch.tensor([1.0, 2.0, -2.0, 0.5])
        adjusted = apply_repetition_penalty(logits, [1, 2], penalty=1.2)
        self.assertLess(adjusted[1].item(), logits[1].item())
        self.assertLess(adjusted[2].item(), logits[2].item())
        self.assertEqual(adjusted[0].item(), logits[0].item())

    def test_top_k_sampling_is_reproducible(self):
        logits = torch.tensor([0.1, 0.2, 0.3, 4.0, 3.0, 2.0])
        first = sample_next_token(
            logits, [], temperature=0.8, top_k=2,
            generator=torch.Generator().manual_seed(42),
        )
        second = sample_next_token(
            logits, [], temperature=0.8, top_k=2,
            generator=torch.Generator().manual_seed(42),
        )
        self.assertEqual(first, second)
        self.assertIn(first, {3, 4})


if __name__ == "__main__":
    unittest.main()
