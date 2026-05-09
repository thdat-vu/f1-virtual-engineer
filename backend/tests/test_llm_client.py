"""Unit tests for ``core.llm.generate_rationale`` itself.

These complement ``test_llm_rationale.py`` (which monkeypatches the wrapper
from above). Here we exercise the wrapper's fail-closed branches directly:
no API key, and exception inside the genai client.
"""

import unittest
from unittest.mock import MagicMock, patch

from core import llm as core_llm


class GenerateRationaleTests(unittest.TestCase):
    def setUp(self):
        core_llm._reset_cache_for_tests()
        # Reset the lazily-configured module so each test re-enters _ensure_configured.
        core_llm._genai_module = None
        core_llm._configured_key = None

    def test_returns_none_when_api_key_missing(self):
        with patch.dict("os.environ", {}, clear=False):
            # Drop the key whether or not it's present in the dev environment.
            import os

            os.environ.pop("GEMINI_API_KEY", None)
            result = core_llm.generate_rationale({"x": 1})
        self.assertIsNone(result)

    def test_returns_none_on_exception(self):
        fake_genai = MagicMock()
        fake_genai.GenerativeModel.side_effect = RuntimeError("boom")

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch.object(core_llm, "_ensure_configured", return_value=fake_genai):
                result = core_llm.generate_rationale({"x": 2})

        self.assertIsNone(result)
        fake_genai.GenerativeModel.assert_called_once()

    def test_returns_none_when_response_text_empty(self):
        fake_response = MagicMock()
        fake_response.text = "   "  # whitespace only — should be treated as empty
        fake_client = MagicMock()
        fake_client.generate_content.return_value = fake_response
        fake_genai = MagicMock()
        fake_genai.GenerativeModel.return_value = fake_client

        with patch.object(core_llm, "_ensure_configured", return_value=fake_genai):
            result = core_llm.generate_rationale({"x": 3})

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
