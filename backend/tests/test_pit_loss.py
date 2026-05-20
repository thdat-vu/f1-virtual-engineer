"""Tests for the pit-loss table + undercut break-even math (#168 slice 1C)."""

from __future__ import annotations

import unittest

from tools.pit_loss import (
    DEFAULT_PIT_LOSS_SECONDS,
    estimate_undercut_break_even_laps,
    lookup_pit_loss_seconds,
)


class LookupPitLossTests(unittest.TestCase):
    def test_known_track_returns_table_value(self):
        self.assertEqual(lookup_pit_loss_seconds("Japanese Grand Prix"), 22.0)
        self.assertEqual(lookup_pit_loss_seconds("Monaco Grand Prix"), 17.5)
        # Singapore is the slowest pit lane on the calendar — verify the
        # table preserves the gap to median (we use it in HUD framing).
        self.assertEqual(lookup_pit_loss_seconds("Singapore Grand Prix"), 26.0)

    def test_match_is_case_insensitive_and_substring(self):
        # "Japan GP" should still match the JAPAN keyword.
        self.assertEqual(lookup_pit_loss_seconds("Japan GP"), 22.0)
        self.assertEqual(lookup_pit_loss_seconds("japanese grand prix"), 22.0)

    def test_unknown_track_returns_default(self):
        # Future or hypothetical events fall back to the table median —
        # better than blanking the panel.
        self.assertEqual(lookup_pit_loss_seconds("Mars Grand Prix"), DEFAULT_PIT_LOSS_SECONDS)

    def test_none_or_empty_event_returns_default(self):
        self.assertEqual(lookup_pit_loss_seconds(None), DEFAULT_PIT_LOSS_SECONDS)
        self.assertEqual(lookup_pit_loss_seconds(""), DEFAULT_PIT_LOSS_SECONDS)


class EstimateUndercutBreakEvenLapsTests(unittest.TestCase):
    def test_break_even_uses_degradation_plus_fresh_tyre_bonus(self):
        # gap 1.4s, degradation 0.3s/lap → advantage ~0.8s/lap → 2 laps.
        result = estimate_undercut_break_even_laps(
            gap_seconds=1.4, degradation_per_lap=0.3
        )
        self.assertEqual(result, 2)

    def test_larger_gap_takes_more_laps(self):
        # gap 4.0s, degradation 0.5s/lap → advantage 1.0s/lap → 4 laps.
        result = estimate_undercut_break_even_laps(
            gap_seconds=4.0, degradation_per_lap=0.5
        )
        self.assertEqual(result, 4)

    def test_negative_or_zero_gap_returns_none(self):
        # Already ahead — undercut math doesn't apply, UI hides the line.
        self.assertIsNone(
            estimate_undercut_break_even_laps(gap_seconds=0.0, degradation_per_lap=0.3)
        )
        self.assertIsNone(
            estimate_undercut_break_even_laps(gap_seconds=-1.0, degradation_per_lap=0.3)
        )

    def test_zero_degradation_still_estimates_using_fresh_tyre_bonus(self):
        # Even with no observed degradation, fresh tyres beat used by ~0.5s/lap;
        # the projection should still resolve.
        result = estimate_undercut_break_even_laps(
            gap_seconds=1.0, degradation_per_lap=0.0
        )
        self.assertEqual(result, 2)  # ceil(1.0 / 0.5)

    def test_minimum_one_lap(self):
        # A tiny gap shouldn't return 0 — that would imply "already done" which
        # is misleading; UI wants at least "next lap".
        result = estimate_undercut_break_even_laps(
            gap_seconds=0.1, degradation_per_lap=0.3
        )
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
