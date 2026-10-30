import unittest

from generate_curriculum import make_examples


class GeneratedCurriculumTests(unittest.TestCase):
    def test_generation_is_reproducible_and_well_formed(self):
        first = make_examples(100, 1234)
        second = make_examples(100, 1234)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 100)
        for item in first:
            self.assertIn("### Usuario:", item["text"])
            self.assertIn("### JARVIS:", item["text"])
            self.assertTrue(item["category"])


if __name__ == "__main__":
    unittest.main()
