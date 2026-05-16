#!/bin/sh
set -eu

mode="${1:---staged}"

collect_all_files() {
  {
    git ls-files -- backend frontend .codex 2>/dev/null || true
    git ls-files --others --exclude-standard -- backend frontend .codex 2>/dev/null || true
  } | grep -Ev '(^frontend/node_modules/|^frontend/\.next/|/__pycache__/|\.pyc$|^backend/data/|^backend/\.env$|^frontend/\.env\.local$)' | sort -u
}

run_backend_checks() {
  echo "[self-qa] Running backend tests..."
  # Detect pytest by importability, not by running the full suite —
  # using a test run as the "is pytest installed?" probe meant a single
  # failing test silently flipped us to the unittest fallback (which
  # collects tests differently and produced its own confusing failures).
  # The check we actually want — "does pytest exist?" — is answered in
  # well under 100ms by import.
  if python3 -c 'import pytest' >/dev/null 2>&1; then
    PYTHONPATH=backend python3 -m pytest backend/tests
  else
    echo "[self-qa] pytest unavailable; falling back to unittest discovery."
    PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p 'test_*.py'
  fi
}

case "$mode" in
  --staged)
    files="$(git diff --cached --name-only --diff-filter=ACM || true)"
    ;;
  --changed)
    files="$(git diff --name-only --diff-filter=ACM HEAD || true)"
    ;;
  --all)
    files="$(collect_all_files)"
    ;;
  *)
    echo "Usage: $0 [--staged|--changed|--all]"
    exit 1
    ;;
esac

if [ -z "$files" ]; then
  echo "No matching files for self-QA."
  exit 0
fi

echo "Files considered for self-QA:"
printf '%s\n' "$files"

need_backend=0
need_frontend=0
need_skill_validate=0
need_shell_syntax=0

if printf '%s\n' "$files" | grep -Eq '^backend/.*\.(py|txt)$|^backend/Dockerfile$'; then
  need_backend=1
fi

if printf '%s\n' "$files" | grep -Eq '^frontend/.*\.(ts|tsx|js|jsx|css|json)$|^frontend/.*\.(config|env)\.[a-z]+$'; then
  need_frontend=1
fi

if printf '%s\n' "$files" | grep -q '^\.codex/skills/.*/SKILL\.md$'; then
  need_skill_validate=1
fi

if printf '%s\n' "$files" | grep -Eq '^(\.codex/scripts/|\.codex/git-hooks/)'; then
  need_shell_syntax=1
fi

if [ "$need_backend" -eq 1 ]; then
  run_backend_checks
fi

if [ "$need_frontend" -eq 1 ]; then
  echo "[self-qa] Running frontend lint & build..."
  (
    cd frontend
    npm run lint
    npm run build
  )
fi

if [ "$need_skill_validate" -eq 1 ]; then
  echo "[self-qa] Validating changed Codex skills..."
  printf '%s\n' "$files" \
    | grep -E '^\.codex/skills/[^/]+/SKILL\.md$' \
    | sed -E 's#^(\.codex/skills/[^/]+)/SKILL\.md$#\1#' \
    | sort -u \
    | while IFS= read -r skill_dir; do
        [ -n "$skill_dir" ] || continue
        python3 /Users/thanhdatvu/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill_dir"
      done
fi

if [ "$need_shell_syntax" -eq 1 ]; then
  echo "[self-qa] Checking shell script syntax..."
  printf '%s\n' "$files" \
    | grep -E '^(\.codex/scripts/|\.codex/git-hooks/)' \
    | while IFS= read -r shell_file; do
        [ -f "$shell_file" ] || continue
        sh -n "$shell_file"
      done
fi

echo "Self-QA completed."
