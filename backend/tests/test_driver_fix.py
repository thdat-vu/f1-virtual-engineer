import unittest
from agents.race_engineer import parse_query_intent, analyze_query, reset_memory_store
from tests._helpers import force_template_rationale
from unittest.mock import patch

class TestDriverFix(unittest.TestCase):
    def setUp(self):
        reset_memory_store()
        force_template_rationale()

    def test_detect_full_name_verstappen(self):
        intent = parse_query_intent("How is Verstappen's pace?")
        self.assertEqual(intent["driver"], "VER")
        self.assertFalse(intent["needs_clarification"])

    def test_detect_full_name_hamilton(self):
        intent = parse_query_intent("Tell me about Hamilton strategy")
        self.assertEqual(intent["driver"], "HAM")
        self.assertEqual(intent["intent_type"], "strategy")

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_memory_fallback_logic(self, mock_summary):
        mock_summary.return_value = {
            "driver": "MOCK", "year": 2023, "event": "Japanese Grand Prix", "session_type": "R",
            "speed": {"avg": 250, "min": 240, "max": 260, "unit": "km/h"}, 
            "gear": {"avg": 7}, "rpm": {"avg": 12000},
            "fallback": False
        }
        
        # 1. Ask about HAM
        analyze_query("HAM telemetry")
        
        # 2. Ask about Verstappen (detected by regex)
        analyze_query("What is Verstappen's speed?")
            
        # 3. Ask a vague question (should fallback to VER)
        res = analyze_query("show again")
        self.assertEqual(res["intent"]["driver"], "VER")

    def test_no_fallback_on_long_unrelated_query(self):
        # 1. Seed memory with HAM
        with patch("agents.race_engineer.get_session_telemetry_summary") as mock_ham:
            mock_ham.return_value = {"driver": "HAM", "fallback": False, "speed": {"avg": 100}, "gear": {"avg": 1}, "rpm": {"avg": 1}, "event": "Japan", "year": 2023, "session_type": "R"}
            analyze_query("HAM telemetry")
            
        # 2. Ask a long query that doesn't mention a driver and isn't a clear follow-up
        res = analyze_query("I want to see the data for the fastest lap in the race session but I forgot who did it")
        self.assertTrue(res["intent"]["needs_clarification"])
        self.assertIn("Please provide a 3-letter driver code", res["response_text"])

if __name__ == "__main__":
    unittest.main()
