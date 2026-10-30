import json
import tempfile
import unittest
from pathlib import Path

from tokenizer import ByteTokenizer
from train_sft import encode_pair, load_pairs


class InstructionTuningTests(unittest.TestCase):
    def test_synthetic_math_is_excluded_from_sft_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authored = {"text": "### Usuario:\n¿Qué es una API?\n### JARVIS:\nUna interfaz de programación."}
            generated = {"text": "### Usuario:\nCalcula 4 + 2.\n### JARVIS:\n4 + 2 = 6."}
            (root / "jarvis_core.jsonl").write_text(json.dumps(authored) + "\n", encoding="utf-8")
            (root / "zz_generated_curriculum.jsonl").write_text(json.dumps(generated) + "\n", encoding="utf-8")
            self.assertEqual(len(load_pairs(root)), 1)
            self.assertEqual(len(load_pairs(root, include_generated=True)), 2)

    def test_prompt_tokens_are_masked_and_answer_is_trained(self):
        inputs, targets = encode_pair(
            "¿Qué eres?",
            "Soy JARVIS, un asistente propio.",
            ByteTokenizer(),
            context=128,
        )
        self.assertEqual(len(inputs), 128)
        self.assertEqual(len(targets), 128)
        valid = [index for index, value in enumerate(targets) if value != -100]
        self.assertTrue(valid)
        self.assertGreater(valid[0], 0)
        self.assertTrue(all(value == -100 for value in targets[:valid[0]]))
        self.assertIn(257, targets)

    def test_answer_is_preserved_when_prompt_is_long(self):
        inputs, targets = encode_pair(
            "pregunta " * 100,
            "RESPUESTA FINAL",
            ByteTokenizer(),
            context=64,
        )
        self.assertEqual(len(inputs), 64)
        self.assertEqual(len(targets), 64)
        trained = [value for value in targets if value != -100]
        decoded = ByteTokenizer().decode([value for value in trained if 0 <= value < 256])
        self.assertTrue(decoded.startswith("RESPUESTA"))


if __name__ == "__main__":
    unittest.main()
