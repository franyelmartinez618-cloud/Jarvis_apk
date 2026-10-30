import unittest

from train import split_documents


class TrainingSplitTests(unittest.TestCase):
    def test_validation_uses_whole_documents(self):
        docs = [f"Documento {i} con contenido independiente." for i in range(20)]
        corpus = "\\n\\n<|document|>\\n\\n".join(docs)
        train, validation = split_documents(corpus, seed=17)
        self.assertTrue(train)
        self.assertTrue(validation)
        self.assertEqual(len(train) + len(validation), len(docs))
        self.assertTrue(set(train).isdisjoint(validation))

    def test_split_is_reproducible(self):
        corpus = "\\n\\n<|document|>\\n\\n".join(
            f"Documento independiente número {i}." for i in range(30)
        )
        self.assertEqual(split_documents(corpus, 2026), split_documents(corpus, 2026))

    def test_single_document_is_rejected(self):
        with self.assertRaises(SystemExit):
            split_documents("Solo un documento no permite validación independiente.", 1)


if __name__ == "__main__":
    unittest.main()
