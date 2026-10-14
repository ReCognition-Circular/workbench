from django.test import TestCase

from checklists.views import (
    _cedar_component_status,
    _is_skip_value,
    _is_pass_value,
)


class CedarComponentStatusTests(TestCase):
    """Section 6.2 - Cedar returns Pass / Fail / Skipped; map to True / False / None."""

    def test_plain_pass(self):
        self.assertIs(_cedar_component_status({"result": "Pass"}), True)

    def test_plain_fail(self):
        self.assertIs(_cedar_component_status({"result": "Fail"}), False)

    def test_plain_skipped_is_none(self):
        self.assertIsNone(_cedar_component_status({"result": "Skipped"}))

    def test_unrecognised_value_is_none_not_pass(self):
        # Fail-safe: an unknown result must never be silently a pass.
        self.assertIsNone(_cedar_component_status({"result": "Frobnicated"}))

    def test_empty_component_is_none(self):
        # Nothing recorded is not a pass.
        self.assertIsNone(_cedar_component_status({}))

    def test_none_component_is_none(self):
        self.assertIsNone(_cedar_component_status(None))

    def test_nested_fail_wins_over_skip(self):
        # Any explicit fail beats a skip (design section 6.2 precedence).
        component = {
            "tests": {
                "eth0": {"result": "Skipped"},
                "wlan0": {"result": "Fail"},
            }
        }
        self.assertIs(_cedar_component_status(component), False)

    def test_nested_skip_with_passes_is_none(self):
        component = {
            "tests": {
                "eth0": {"result": "Pass"},
                "wlan0": {"result": "Skipped"},
            }
        }
        self.assertIsNone(_cedar_component_status(component))

    def test_all_nested_pass(self):
        component = {
            "tests": {
                "eth0": {"result": "Pass"},
                "wlan0": {"result": "Pass"},
            }
        }
        self.assertIs(_cedar_component_status(component), True)

    def test_skip_spellings(self):
        for value in ("Skipped", "skipped", "SKIPPED", "skip", "N/A", "n/a"):
            with self.subTest(value=value):
                self.assertIsNone(_cedar_component_status({"result": value}))

    def test_case_insensitive_pass_and_fail(self):
        self.assertIs(_cedar_component_status({"result": "PASS"}), True)
        self.assertIs(_cedar_component_status({"result": "fail"}), False)


class CedarSkipHelperTests(TestCase):
    """The building blocks underneath the tri-state helper."""

    def test_is_skip_value(self):
        self.assertTrue(_is_skip_value("Skipped"))
        self.assertTrue(_is_skip_value(" N/A "))
        self.assertFalse(_is_skip_value("Pass"))
        self.assertFalse(_is_skip_value("Fail"))
        self.assertFalse(_is_skip_value(None))
        self.assertFalse(_is_skip_value(""))

    def test_is_pass_value_unchanged(self):
        # Guard: the legacy two-state helper keeps its old behaviour,
        # because the QA panel and grade calc still depend on it.
        self.assertTrue(_is_pass_value("Pass"))
        self.assertFalse(_is_pass_value("Fail"))
        self.assertTrue(_is_pass_value("Skipped"))
        self.assertTrue(_is_pass_value(None))
