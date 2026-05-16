---
name: f1-ui-motion-designer
description: Apply Apple-meets-automotive UI/UX direction when designing or refining the F1 Virtual Engineer interface — typography, glass surfaces, telemetry-as-hero composition, motion choreography. Use when a task touches landing pages, mission-control layouts, dashboard panels, telemetry visualizations, or any user-facing surface where visual hierarchy and motion timing matter.
---

# Skill: F1 UI/UX Motion Designer (Apple x Automotive Edition)

Expert guide for transforming the F1 Virtual Engineer interface into a high-precision "Operator Surface".

## Design Philosophy: "Surgical Mission Control"
- **Data as the Hero**: AI does not "talk", it "annotates". Telemetry charts (FastF1) are the primary visual, AI insights are HUD overlays.
- **Apple Aesthetic**: 
  - Typography: SF Pro Display / Neo-Grotesk (Large, monumental headers, tracking -0.02em).
  - Material: Glassmorphism (Background blur 20px, subtle borders 0.5px white/10%).
  - Layout: Radical subtraction. If a pixel doesn't convey data, remove it.
- **Automotive Precision**: Zero-radius buttons, monospace data labels, and high-contrast "Chiaroscuro" (Deep blacks vs targeted highlights).

## Automotive Palette & Theme Map
| Theme | Style | Primary | Surface | Accents |
| :--- | :--- | :--- | :--- | :--- |
| **Default (Apex)** | Racing Dark | #020617 | #0F172A | #EF4444 (Red-600) |
| **Ferrari** | Editorial | #FFFFFF | #000000 | #FF2800 (Rosso Corsa) |
| **Mercedes** | Silver Arrow | #00A19B | #1E1E1E | #C0C0C0 (Silver) |
| **Red Bull** | Racing Bold | #0600EF | #000B21 | #FFEC00 (Yellow) |
| **BMW** | Luxury Eng. | #FFFFFF | #1A1A1A | #0066B2 (BMW Blue) |
| **Tesla** | Radical Sub. | #E2E2E2 | #000000 | #CC0000 (Red) |
| **Bugatti** | Hypercar | #000000 | #000000 | #0000FF (Bugatti Blue) |

## Layout Rules (The "Cockpit" Grid)
1. **The Navigation (Left)**: Thin sidebar (64px) for global mode switching (Live, Replay, Analytics).
2. **The Command Center (Top)**: Minimal status bar (Active Driver, Session Time, Track Temp).
3. **The Canvas (Center)**: 70% of viewport. Multi-layered FastF1 telemetry charts.
4. **The Intelligence HUD (Right)**: Vertical drawer for AI Strategy recommendations and reasoning traces.

## Motion & Interaction
- **Entrance**: Cinematic fades for monumental headers.
- **Data updates**: Subtle "shimmer" effect when new telemetry arrives.
- **Hover**: 0.5px border glow using the Team's Primary color.
