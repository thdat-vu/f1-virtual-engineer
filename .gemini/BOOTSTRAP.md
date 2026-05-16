# Gemini Bootstrap: Auto-Load Protocol

This folder contains the operating system for Gemini within the F1 Virtual Engineer project.

## Initialization Sequence
Every time a new session starts, the Agent MUST:
1.  **Read Mandates**: Load `.gemini/MANDATES.md` to understand core constraints.
2.  **Load Skills**: Recursively read all files in `.gemini/skills/`.
3.  **Compaction Check**: If context history is deep, summarize key decisions into a "Working Checkpoint" before proceeding.

## Harness Patterns (Autonomous Mode)
- **Generator-Evaluator**: When implementing complex logic, I will first write the implementation (Generator) then peer-review it against mandates (Evaluator) before asking for user approval.
- **Continuous Grader**: Use `/quality-gate` skills to prove correctness after every atomic edit.

## Skills Directory Guide
- `f1-data-expert.md`: Deep knowledge of FastF1 and race telemetry.
- `ui-ux-automotive.md`: Design system rules (Apple x Automotive).
- `indie-hacker-workflow.md`: Standardized `Indie Launch Loop` implementation.

## Automation Flows
- `pre-commit.sh`: Automated QA before any commit.
- `pr-generator.md`: Template for generating high-quality PR descriptions.
