import unittest
from unittest.mock import patch

from agents.race_engineer import (
    MEMORY_RETENTION_CAP,
    MAX_TOOL_RETRIES,
    MEMORY_STORE,
    analyze_query,
    parse_query_intent,
    parse_telemetry_intent,
    reset_memory_store,
)
from tests._helpers import force_template_rationale


def build_telemetry_fixture(driver: str, year: int, session_type: str, event: str = "Japanese Grand Prix") -> dict:
    driver = driver.upper()
    speed_base = {"HAM": 255.0, "VER": 258.0, "NOR": 252.0}.get(driver, 250.0)
    if session_type == "Q":
        speed_base += 3.0
    return {
        "driver": driver,
        "year": year,
        "event": event,
        "session_type": session_type,
        "sample_points": 3,
        "speed": {"min": speed_base - 5.0, "max": speed_base + 5.0, "avg": speed_base, "unit": "km/h"},
        "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
        "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
        "source": "fastf1",
        "fallback": False,
        "fallback_reason": None,
    }


class RaceEngineerTests(unittest.TestCase):
    def setUp(self):
        reset_memory_store()
        force_template_rationale()

    def test_parse_telemetry_intent_requires_driver(self):
        intent = parse_telemetry_intent("toc do o japanese gp 2023")
        self.assertTrue(intent["needs_clarification"])
        self.assertIsNotNone(intent["clarification_message"])

    def test_parse_telemetry_intent_extracts_driver_and_year(self):
        intent = parse_telemetry_intent("show HAM speed at japan 2023 race")
        self.assertFalse(intent["needs_clarification"])
        self.assertEqual(intent["driver"], "HAM")
        self.assertEqual(intent["year"], 2023)
        self.assertEqual(intent["session_type"], "R")

    def test_parse_telemetry_intent_asks_clarification_for_multiple_drivers(self):
        intent = parse_telemetry_intent("compare HAM vs VER in japan 2023")
        self.assertTrue(intent["needs_clarification"])
        self.assertIn("Multiple driver codes detected", intent["clarification_message"])

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_analyze_query_returns_formatted_telemetry_text(self, mock_summary):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 3,
            "speed": {"min": 250.0, "max": 260.0, "avg": 255.0, "unit": "km/h"},
            "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
            "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": False,
            "fallback_reason": None,
        }
        result = analyze_query("ham japan 2023 race telemetry")

        self.assertIn("HAM telemetry", result["response_text"])
        self.assertIsNone(result["error"])
        self.assertFalse(result["telemetry_data"]["fallback"])
        self.assertEqual(result["execution"]["termination_reason"], "completed")
        self.assertEqual(result["execution"]["step_limit"], 6)
        self.assertIsInstance(result["execution"]["trace"], list)
        self.assertEqual(result["retry"]["count"], 0)
        self.assertEqual(result["citations"], [])

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_analyze_query_attaches_citations_when_query_mentions_regulations(self, mock_summary):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 3,
            "speed": {"min": 250.0, "max": 260.0, "avg": 255.0, "unit": "km/h"},
            "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
            "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": False,
            "fallback_reason": None,
        }
        result = analyze_query("ham japan 2023 race DRS rules")
        self.assertTrue(result["citations"], "expected DRS citation for regulation query")
        self.assertEqual(result["citations"][0]["id"], "drs-activation")

    @patch("agents.race_engineer.strategy_analyzer")
    def test_analyze_query_attaches_citations_for_strategy_intent(self, mock_strategy):
        # Strategy queries should also fetch citations even without explicit
        # FIA-vocabulary keywords. The strategy-notes corpus is the whole
        # point of slice B (#197); without this trigger the LLM can't ground
        # its rationale in things like "undercut" / "tyre cliff".
        mock_strategy.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "strategy": {
                "recommended_pit_window_laps": [18, 22],
                "confidence_band": "medium",
                "undercut_risk": "medium",
            },
            "fallback": False,
            "fallback_reason": None,
        }
        result = analyze_query("should HAM undercut now in japan 2023 race")
        self.assertTrue(result["citations"], "expected strategy citation for undercut query")
        ids = [c["id"] for c in result["citations"]]
        self.assertIn("strategy-undercut", ids)

    @patch("agents.race_engineer.knowledge_lookup")
    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_analyze_query_citation_failure_is_swallowed(self, mock_summary, mock_lookup):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 3,
            "speed": {"min": 250.0, "max": 260.0, "avg": 255.0, "unit": "km/h"},
            "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
            "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": False,
            "fallback_reason": None,
        }
        mock_lookup.side_effect = RuntimeError("index unavailable")
        result = analyze_query("ham japan 2023 race pit lane speed penalty")
        self.assertEqual(result["citations"], [])
        self.assertIsNone(result["error"])

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_analyze_query_uses_memory_for_follow_up_without_driver(self, mock_summary):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 3,
            "speed": {"min": 250.0, "max": 260.0, "avg": 255.0, "unit": "km/h"},
            "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
            "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": False,
            "fallback_reason": None,
        }
        first = analyze_query("ham japan 2023 race telemetry")
        second = analyze_query("show speed again")

        self.assertEqual(first["intent"]["driver"], "HAM")
        self.assertEqual(second["intent"]["driver"], "HAM")
        self.assertIsNone(second["error"])
        self.assertGreaterEqual(second["memory"]["history_size"], 2)

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_follow_up_comparison_without_driver_requires_clarification(self, mock_summary):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 3,
            "speed": {"min": 250.0, "max": 260.0, "avg": 255.0, "unit": "km/h"},
            "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
            "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": False,
            "fallback_reason": None,
        }
        analyze_query("ham japan 2023 race telemetry")
        follow_up = analyze_query("compare with him")

        self.assertIsNotNone(follow_up["error"])
        self.assertIn("Comparison query detected", follow_up["error"])

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_memory_store_respects_retention_cap(self, mock_summary):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 3,
            "speed": {"min": 250.0, "max": 260.0, "avg": 255.0, "unit": "km/h"},
            "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
            "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": False,
            "fallback_reason": None,
        }
        last = None
        for _ in range(MEMORY_RETENTION_CAP + 5):
            last = analyze_query("ham japan 2023 race telemetry")

        self.assertIsNotNone(last)
        self.assertEqual(last["memory"]["history_size"], MEMORY_RETENTION_CAP)
        self.assertEqual(last["memory"]["retention_cap"], MEMORY_RETENTION_CAP)


    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_multi_turn_regression_canonical_flows(self, mock_summary):
        def telemetry_side_effect(*, year, event, session_type, driver):
            return build_telemetry_fixture(driver=driver, year=year, session_type=session_type, event=event)

        mock_summary.side_effect = telemetry_side_effect

        canonical_flows = [
            {
                "name": "same driver carry-over",
                "steps": [
                    {
                        "query": "ham japan 2023 race telemetry",
                        "expected": {"driver": "HAM", "year": 2023, "session_type": "R", "history_size": 1},
                    },
                    {
                        "query": "show speed again",
                        "expected": {"driver": "HAM", "year": 2023, "session_type": "R", "history_size": 2},
                    },
                ],
            },
            {
                "name": "driver switch becomes new memory anchor",
                "steps": [
                    {
                        "query": "ham japan 2023 race telemetry",
                        "expected": {"driver": "HAM", "year": 2023, "session_type": "R", "history_size": 1},
                    },
                    {
                        "query": "show VER telemetry",
                        "expected": {"driver": "VER", "year": 2023, "session_type": "R", "history_size": 2},
                    },
                    {
                        "query": "show speed again",
                        "expected": {"driver": "VER", "year": 2023, "session_type": "R", "history_size": 3},
                    },
                ],
            },
            {
                "name": "session switch carries forward",
                "steps": [
                    {
                        "query": "ham japan 2023 race telemetry",
                        "expected": {"driver": "HAM", "year": 2023, "session_type": "R", "history_size": 1},
                    },
                    {
                        "query": "ham japan 2023 qualifying telemetry",
                        "expected": {"driver": "HAM", "year": 2023, "session_type": "Q", "history_size": 2},
                    },
                    {
                        "query": "show speed again",
                        "expected": {"driver": "HAM", "year": 2023, "session_type": "Q", "history_size": 3},
                    },
                ],
            },
        ]

        for flow in canonical_flows:
            with self.subTest(flow=flow["name"]):
                reset_memory_store()
                for index, step in enumerate(flow["steps"], start=1):
                    result = analyze_query(step["query"])

                    self.assertIsNone(result["error"], msg=f"flow={flow['name']} step={index}")
                    self.assertEqual(result["intent"]["driver"], step["expected"]["driver"])
                    self.assertEqual(result["intent"]["year"], step["expected"]["year"])
                    self.assertEqual(result["intent"]["session_type"], step["expected"]["session_type"])
                    self.assertEqual(result["telemetry_data"]["driver"], step["expected"]["driver"])
                    self.assertEqual(result["telemetry_data"]["year"], step["expected"]["year"])
                    self.assertEqual(result["telemetry_data"]["session_type"], step["expected"]["session_type"])
                    self.assertEqual(result["memory"]["last_driver"], step["expected"]["driver"])
                    self.assertEqual(result["memory"]["history_size"], step["expected"]["history_size"])

                    latest_memory = MEMORY_STORE[-1]
                    self.assertEqual(latest_memory["last_driver"], step["expected"]["driver"])
                    self.assertEqual(latest_memory["last_year"], step["expected"]["year"])
                    self.assertEqual(latest_memory["last_session_type"], step["expected"]["session_type"])

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_retry_policy_recovers_from_transient_fallback(self, mock_summary):
        mock_summary.side_effect = [
            {
                "driver": "HAM",
                "year": 2023,
                "event": "Japanese Grand Prix",
                "session_type": "R",
                "sample_points": 0,
                "speed": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "km/h"},
                "gear": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "gear"},
                "rpm": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "rpm"},
                "source": "fastf1",
                "fallback": True,
                "fallback_reason": "Connection timeout to provider",
            },
            {
                "driver": "HAM",
                "year": 2023,
                "event": "Japanese Grand Prix",
                "session_type": "R",
                "sample_points": 3,
                "speed": {"min": 250.0, "max": 260.0, "avg": 255.0, "unit": "km/h"},
                "gear": {"min": 7.0, "max": 8.0, "avg": 7.3, "unit": "gear"},
                "rpm": {"min": 12000.0, "max": 12500.0, "avg": 12300.0, "unit": "rpm"},
                "source": "fastf1",
                "fallback": False,
                "fallback_reason": None,
            },
        ]
        result = analyze_query("ham japan 2023 race telemetry")
        self.assertEqual(mock_summary.call_count, 2)
        self.assertEqual(result["retry"]["count"], 1)
        self.assertFalse(result["retry"]["retryable_exhausted"])

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_retry_policy_stops_after_max_attempts(self, mock_summary):
        mock_summary.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "sample_points": 0,
            "speed": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "km/h"},
            "gear": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "gear"},
            "rpm": {"min": 0.0, "max": 0.0, "avg": 0.0, "unit": "rpm"},
            "source": "fastf1",
            "fallback": True,
            "fallback_reason": "Connection timeout to provider",
        }
        result = analyze_query("ham japan 2023 race telemetry")
        self.assertEqual(mock_summary.call_count, MAX_TOOL_RETRIES + 1)
        self.assertTrue(result["retry"]["retryable_exhausted"])

    def test_parse_query_intent_detects_strategy(self):
        intent = parse_query_intent("Should HAM pit soon in Japanese GP 2023 race?")
        self.assertEqual(intent["intent_type"], "strategy")
        self.assertEqual(intent["driver"], "HAM")

    @patch("agents.race_engineer.strategy_analyzer")
    def test_analyze_query_returns_strategy_payload(self, mock_strategy):
        mock_strategy.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "strategy": {
                "recommended_pit_window_laps": [8, 14],
                "undercut_risk": "medium",
                "overcut_risk": "low",
                "confidence_band": "medium",
                "assumptions": ["Current gap to rival considered: 1.2s."],
                "rationale": ["Predicted degradation rate: 0.310s/lap."],
            },
        }
        result = analyze_query("Should HAM pit soon in Japanese GP 2023 race?")

        self.assertEqual(result["intent"]["intent_type"], "strategy")
        self.assertIsNotNone(result["strategy_data"])
        self.assertEqual(result["strategy_data"]["confidence_band"], "medium")
        self.assertIn("Baseline strategy recommendation", result["response_text"])

    @patch("agents.race_engineer.strategy_analyzer")
    def test_strategy_follow_up_uses_memory_context(self, mock_strategy):
        mock_strategy.return_value = {
            "driver": "HAM",
            "year": 2023,
            "event": "Japanese Grand Prix",
            "session_type": "R",
            "fallback": False,
            "fallback_reason": None,
            "strategy": {
                "recommended_pit_window_laps": [8, 14],
                "undercut_risk": "medium",
                "overcut_risk": "low",
                "confidence_band": "medium",
                "assumptions": ["Current gap to rival considered: 1.2s."],
                "rationale": ["Predicted degradation rate: 0.310s/lap."],
            },
        }
        analyze_query("ham japan 2023 race telemetry")
        follow_up = analyze_query("Should he pit soon?")

        self.assertEqual(follow_up["intent"]["driver"], "HAM")
        self.assertEqual(follow_up["intent"]["intent_type"], "strategy")
        self.assertIsNotNone(follow_up["strategy_data"])

    @patch("agents.race_engineer.get_session_telemetry_summary")
    def test_analyze_query_honors_session_and_driver_overrides(self, mock_summary):
        mock_summary.return_value = build_telemetry_fixture("VER", 2024, "Q", event="Monaco Grand Prix")

        result = analyze_query(
            "show me the data",
            session_override={"event": "Monaco Grand Prix", "year": 2024, "session_type": "Q"},
            driver_override="VER",
        )

        mock_summary.assert_called_with(
            year=2024,
            event="Monaco Grand Prix",
            session_type="Q",
            driver="VER",
        )
        self.assertEqual(result["intent"]["driver"], "VER")
        self.assertEqual(result["intent"]["year"], 2024)
        self.assertEqual(result["intent"]["event"], "Monaco Grand Prix")
        self.assertEqual(result["intent"]["session_type"], "Q")
        self.assertIsNone(result["error"])


if __name__ == "__main__":
    unittest.main()
