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
    # Original 5 (slice A) — keep so historical comparisons stay valid.
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
    # Slice B expansion (#208 follow-up) — broader circuit coverage so the
    # accuracy number reflects more than one degradation regime. Mixed
    # 2023-2024, mostly winners or podium runners so the first-stop call
    # is a real strategy decision rather than a damaged-car detour.
    {
        "id": "2024-bahrain-r-ver",
        "year": 2024,
        "event": "Bahrain Grand Prix",
        "session_type": "R",
        "driver": "VER",
    },
    {
        "id": "2024-saudi-r-ver",
        "year": 2024,
        "event": "Saudi Arabian Grand Prix",
        "session_type": "R",
        "driver": "VER",
    },
    {
        "id": "2024-australia-r-sai",
        "year": 2024,
        "event": "Australian Grand Prix",
        "session_type": "R",
        "driver": "SAI",
    },
    {
        "id": "2024-china-r-ver",
        "year": 2024,
        "event": "Chinese Grand Prix",
        "session_type": "R",
        "driver": "VER",
    },
    {
        "id": "2024-miami-r-nor",
        "year": 2024,
        "event": "Miami Grand Prix",
        "session_type": "R",
        "driver": "NOR",
    },
    {
        "id": "2024-imola-r-ver",
        "year": 2024,
        "event": "Emilia Romagna Grand Prix",
        "session_type": "R",
        "driver": "VER",
    },
    {
        "id": "2024-canada-r-rus",
        "year": 2024,
        "event": "Canadian Grand Prix",
        "session_type": "R",
        "driver": "RUS",
    },
    {
        "id": "2024-austria-r-rus",
        "year": 2024,
        "event": "Austrian Grand Prix",
        "session_type": "R",
        "driver": "RUS",
    },
    {
        "id": "2024-hungary-r-nor",
        "year": 2024,
        "event": "Hungarian Grand Prix",
        "session_type": "R",
        "driver": "NOR",
    },
    {
        "id": "2024-belgium-r-ham",
        "year": 2024,
        "event": "Belgian Grand Prix",
        "session_type": "R",
        "driver": "HAM",
    },
    {
        "id": "2024-singapore-r-nor",
        "year": 2024,
        "event": "Singapore Grand Prix",
        "session_type": "R",
        "driver": "NOR",
    },
    {
        "id": "2024-mexico-r-sai",
        "year": 2024,
        "event": "Mexico City Grand Prix",
        "session_type": "R",
        "driver": "SAI",
    },
    {
        "id": "2024-brazil-r-ver",
        "year": 2024,
        "event": "São Paulo Grand Prix",
        "session_type": "R",
        "driver": "VER",
    },
    {
        "id": "2024-vegas-r-rus",
        "year": 2024,
        "event": "Las Vegas Grand Prix",
        "session_type": "R",
        "driver": "RUS",
    },
    {
        "id": "2023-bahrain-r-ver",
        "year": 2023,
        "event": "Bahrain Grand Prix",
        "session_type": "R",
        "driver": "VER",
    },
]
