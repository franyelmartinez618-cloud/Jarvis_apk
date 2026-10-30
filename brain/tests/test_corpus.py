import unittest
from pathlib import Path

from prepare_corpus import provenance_for


class CorpusProvenanceTests(unittest.TestCase):
    def test_seed_is_marked_as_original_project_material(self):
        provenance = provenance_for(Path("data/seed/sample.txt"), Path("data/seed"), None)
        self.assertEqual(provenance["license"], "Owner-Created")
        self.assertTrue(provenance["training_allowed"])

    def test_cc0_source_with_explicit_rights_is_accepted(self):
        source = Path("data/raw")
        item = {
            "file": "facts.txt",
            "source": "Original public-domain source",
            "license": "CC0-1.0",
            "training_allowed": True,
            "commercial_use": True,
        }
        provenance = provenance_for(source / "facts.txt", source, [item])
        self.assertEqual(provenance["license"], "CC0-1.0")

    def test_noncommercial_or_unknown_license_is_rejected(self):
        source = Path("data/raw")
        item = {
            "file": "book.txt",
            "license": "CC-BY-NC-SA-4.0",
            "training_allowed": True,
            "commercial_use": False,
        }
        with self.assertRaises(SystemExit):
            provenance_for(source / "book.txt", source, [item])

    def test_apache_source_requires_license_copy_and_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "LICENSE").write_text("Apache License\nVersion 2.0", encoding="utf-8")
            item = {
                "file": "oasst_es_human.jsonl",
                "source": "OpenAssistant OASST1",
                "license": "Apache-2.0",
                "training_allowed": True,
                "commercial_use": True,
                "attribution": "OpenAssistant contributors, OASST1",
                "license_text_file": "LICENSE",
            }
            provenance = provenance_for(source / item["file"], source, [item])
            self.assertEqual(provenance["license"], "Apache-2.0")
        with self.assertRaises(SystemExit):
            provenance_for(Path("data/raw/no-copy.jsonl"), Path("data/raw"), [{
                "file": "no-copy.jsonl", "license": "Apache-2.0",
                "training_allowed": True, "commercial_use": True,
            }])

    def test_cc_by_requires_attribution(self):
        source = Path("data/raw")
        item = {
            "file": "article.txt",
            "license": "CC-BY-4.0",
            "training_allowed": True,
            "commercial_use": True,
        }
        with self.assertRaises(SystemExit):
            provenance_for(source / "article.txt", source, [item])


if __name__ == "__main__":
    unittest.main()
