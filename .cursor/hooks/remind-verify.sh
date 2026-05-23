#!/bin/sh
set -eu

input="$(cat)"

# Keep this hook non-blocking: it only logs actionable reminders.
if printf "%s" "$input" | python3 -c '
import sys
data = sys.stdin.read().lower()
sys.exit(0 if "frontend/" in data else 1)
'; then
  printf '%s\n' "Hook reminder: edited frontend file. Run: cd frontend && yarn lint"
elif printf "%s" "$input" | python3 -c '
import sys
data = sys.stdin.read().lower()
sys.exit(0 if "backend/" in data else 1)
'; then
  printf '%s\n' "Hook reminder: edited backend file. Run: python -m pytest (or targeted tests)"
else
  printf '%s\n' "Hook reminder: run the smallest relevant lint/test for your change."
fi

exit 0
