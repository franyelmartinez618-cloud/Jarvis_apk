import unittest

from prepare_oasst1 import approved_human_message, build_pairs


def message(message_id, parent_id, role, text, **extra):
    base = {
        "message_id": message_id,
        "parent_id": parent_id,
        "role": role,
        "lang": "es",
        "text": text,
        "deleted": False,
        "review_result": True,
        "synthetic": False,
        "model_name": "",
        "message_tree_id": "tree-1",
        "rank": 0,
        "review_count": 2,
        "labels": {"pii": {"value": 0.0, "count": 3}},
    }
    base.update(extra)
    return base


class OASSTPreparationTests(unittest.TestCase):
    def test_only_human_reviewed_spanish_pairs_are_kept(self):
        prompt = message("p1", None, "prompter", "¿Cómo funciona una API en informática?")
        answer = message("a1", "p1", "assistant", "Una API define operaciones y datos que puede usar otro programa.")
        synthetic = message("a2", "p1", "assistant", "Respuesta generada.", synthetic=True, model_name="some-model")
        english = message("p2", None, "prompter", "What is an API?", lang="en")
        result = build_pairs([prompt, answer, synthetic, english])
        self.assertEqual(len(result), 1)
        self.assertIn("¿Cómo funciona una API", result[0]["text"])
        self.assertIn("Una API define operaciones", result[0]["text"])
        self.assertEqual(result[0]["group_id"], "tree-1")
        self.assertIn("\n### JARVIS:\n", result[0]["text"])

    def test_pii_and_unreviewed_messages_are_rejected(self):
        pii = message("p1", None, "prompter", "Quiero compartir información personal.", labels={"pii": {"value": 1.0, "count": 2}})
        unreviewed = message("p2", None, "prompter", "Esta conversación no fue revisada.", review_result=False)
        self.assertFalse(approved_human_message(pii))
        self.assertFalse(approved_human_message(unreviewed))


if __name__ == "__main__":
    unittest.main()
