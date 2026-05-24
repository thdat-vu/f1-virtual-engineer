"""Fixtures for the strategy pit-accuracy eval (#208).

Each fixture is one historical race-driver pairing whose first pit-stop lap
we want the heuristic to bracket. Ground truth is NOT hardcoded — the
harness derives it at runtime from `get_session_lap_list` (looking for the
first lap where `is_pit_in` is true). Hardcoding lap numbers I cannot
verify would be a black-box claim; deriving from FastF1 keeps the eval
honest and lets it self-correct if the upstream data changes.

Choose scenarios that span:
- different circuits (degradation profiles vary widely),
- the modern hybrid era (2022+) where the helper's tyre model is calibrated,
- recognisable drivers so failures are easy to investigate.
"""

from typing import Any

FIXTURES: list[dict[str, Any]] = [
    {
        "id": "2024-japan-r-ver",
        "year": 2024,
        "event": "Japanese Grand Prix",
        "session_type": "R",
        "driver": "VER",
    },
    {
        "id": "2024-italy-r-lec",
        "year": 2024,
        "event": "Italian Grand Prix",
        "session_type": "R",
        "driver": "LEC",
    },
    {
        "id": "2023-japan-r-ver",
        "year": 2023,
        "event": "Japanese Grand Prix",
        "session_type": "R",
        "driver": "VER",
    },
    {
        "id": "2024-spain-r-nor",
        "year": 2024,
        "event": "Spanish Grand Prix",
        "session_type": "R",
        "driver": "NOR",
    },
    {
        "id": "2024-britain-r-ham",
        "year": 2024,
        "event": "British Grand Prix",
        "session_type": "R",
        "driver": "HAM",
    },
]
