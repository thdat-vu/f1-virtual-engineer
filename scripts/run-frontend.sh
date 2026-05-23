#!/bin/sh
set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/frontend"

# corepack ships with Node 18+; it pins yarn to the version recorded in
# package.json's `packageManager` field so dev / CI / Docker all run the
# same yarn (#171). Skip if already enabled — `corepack enable` is
# idempotent but emits a noisy warning when re-run.
if ! command -v yarn >/dev/null 2>&1; then
  corepack enable
fi

if [ ! -d node_modules ]; then
  yarn install --immutable
fi

exec yarn dev
