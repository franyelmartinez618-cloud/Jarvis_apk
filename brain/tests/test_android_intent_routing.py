import re
import unicodedata
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTER_SOURCE = (ROOT / "scripts" / "prepare_jarvis_local_brain.py").read_text(encoding="utf-8")
VOICE_SOURCE = (ROOT / "scripts" / "prepare_jarvis_voice_unlock.py").read_text(encoding="utf-8")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[¿?¡!.,;]", " ", text)).strip()


def resolve_intent(text: str, last_app: str | None = None) -> tuple[str, str | None, str | None]:
    """Executable behavior spec for the Android routing rules."""
    value = normalize(text)

    compound = re.match(
        r"^(?:por favor )?(?:abre|abrime|abri|abrir|inicia|iniciar|ejecuta|ejecutar|lanza|arranca|ponme|quiero abrir)\s+"
        r"(?:la app |la aplicacion |aplicacion |app |el juego |el )?(.+?)\s+"
        r"(?:y luego|y|luego|despues|para)\s+(?:busca|buscar|encuentra|localiza)\s+(.+)$",
        value,
    )
    if compound:
        return "in_app_search", compound.group(1).strip(), compound.group(2).strip().removeprefix("a ").strip()

    web_after = re.match(
        r"^(?:busca|buscar|buscame|investiga|consulta)\s+(.+?)\s+en\s+(?:google|internet|la web|web|el navegador)$",
        value,
    )
    web_before = re.match(
        r"^(?:busca|buscar|buscame|investiga|consulta)\s+(?:en\s+)?(?:google|internet|la web|web|el navegador)\s+(.+)$",
        value,
    )
    if web_after or web_before:
        match = web_after or web_before
        return "web_search", None, match.group(1).strip()

    app_after = re.match(
        r"^(?:busca|buscar|buscame|encuentra|localiza)\s+(.+?)\s+(?:en|dentro de)\s+"
        r"(?:la app |la aplicacion |app |aplicacion )?(.+)$",
        value,
    )
    if app_after:
        return "in_app_search", app_after.group(2).strip(), app_after.group(1).strip().removeprefix("a ").strip()

    app_before = re.match(
        r"^(?:busca|buscar|buscame|encuentra|localiza)\s+(?:en|dentro de)\s+"
        r"(?:la app |la aplicacion |app |aplicacion )?(.+?)\s+(?:a|sobre|por)\s+(.+)$",
        value,
    )
    if app_before:
        return "in_app_search", app_before.group(1).strip(), app_before.group(2).strip().removeprefix("a ").strip()

    generic = re.match(r"^(?:busca|buscar|buscame|encuentra|localiza)\s+(.+)$", value)
    if generic:
        if last_app:
            return "in_app_search", last_app, generic.group(1).strip().removeprefix("a ").strip()
        return "ask_destination", None, generic.group(1).strip()

    opening = re.match(
        r"^(?:por favor )?(?:abre|abrime|abri|abrir|inicia|iniciar|ejecuta|ejecutar|lanza|arranca|ponme|quiero abrir)\s+(.+)$",
        value,
    )
    if opening:
        return "open_app", opening.group(1).strip(), None

    return "conversation", None, None


class AndroidIntentRoutingTests(unittest.TestCase):
    def test_compound_open_whatsapp_and_search_brother_stays_in_whatsapp(self):
        self.assertEqual(
            resolve_intent("Jarvis, abre WhatsApp y busca a mi hermano"),
            ("in_app_search", "whatsapp", "mi hermano"),
        )

    def test_asr_split_keeps_recently_opened_app_as_context(self):
        self.assertEqual(
            resolve_intent("busca a mi hermano", last_app="WhatsApp"),
            ("in_app_search", "WhatsApp", "mi hermano"),
        )

    def test_explicit_whatsapp_search_does_not_open_browser(self):
        self.assertEqual(
            resolve_intent("busca a mi hermano en WhatsApp"),
            ("in_app_search", "whatsapp", "mi hermano"),
        )

    def test_app_first_search_word_order_is_supported(self):
        self.assertEqual(
            resolve_intent("busca en WhatsApp a mi hermano"),
            ("in_app_search", "whatsapp", "mi hermano"),
        )

    def test_web_requires_explicit_web_destination(self):
        self.assertEqual(
            resolve_intent("busca a mi hermano en internet"),
            ("web_search", None, "a mi hermano"),
        )

    def test_ambiguous_search_asks_instead_of_guessing_web(self):
        self.assertEqual(
            resolve_intent("busca a mi hermano"),
            ("ask_destination", None, "a mi hermano"),
        )

    def test_single_app_open_is_still_supported(self):
        self.assertEqual(
            resolve_intent("abre WhatsApp"),
            ("open_app", "whatsapp", None),
        )

    def test_android_source_uses_the_same_route_before_legacy_parser(self):
        self.assertIn("val openAndSearch = Regex(", ROUTER_SOURCE)
        self.assertIn("val webSearchAfter = Regex(", ROUTER_SOURCE)
        self.assertIn("searchInsideAppForModel(activeApp, query)", ROUTER_SOURCE)
        self.assertIn('openSettingsForModel("accesibilidad")', ROUTER_SOURCE)
        self.assertIn("lastOpenedAppLabel = label", ROUTER_SOURCE)

        route_position = VOICE_SOURCE.index("if (runNaturalPhoneAction(raw)) return")
        parser_position = VOICE_SOURCE.index("when (cmd)", route_position)
        self.assertLess(route_position, parser_position)


if __name__ == "__main__":
    unittest.main()
