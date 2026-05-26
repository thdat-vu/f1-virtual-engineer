# Landing screenshots

Each capability card in `frontend/src/components/landing/CapabilityGrid.tsx`
expects a 2:1 PNG (around 1600x800) at one of the slugs below. These are
authored manually from Mission Control with the relevant session pinned —
treat them as static assets that need a refresh on major UI changes.

| Slug                                | What to capture                                                       |
|-------------------------------------|-----------------------------------------------------------------------|
| `screenshot-telemetry-lap-delta.png`| VER vs HAM at Japan, both telemetry and lap-delta charts visible      |
| `screenshot-strategy-compare.png`   | Strategy compare with two what-if cards side-by-side                  |
| `screenshot-cross-year.png`         | VER 2024 vs 2023 Japan with the citation chip open                    |
| `screenshot-weather-tyre.png`       | Header weather pill + tyre card showing historical compound framing   |

Until the PNGs are dropped in this folder, the cards will render with a
plain background — the build and lint still pass, only the visuals are
missing.
