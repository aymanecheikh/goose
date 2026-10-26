#!/usr/bin/env bash
set -euo pipefail

goose_repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$goose_repo_dir"
source bin/activate-hermit
node scripts/local-ai/prepare-engine.mjs
pnpm --dir ui install --frozen-lockfile
pnpm --dir ui/desktop run package
codesign --force --deep --sign - --entitlements ui/desktop/entitlements.plist \
  "ui/desktop/out/Goose Local-darwin-arm64/Goose Local.app"
printf 'Built: %s\n' "$goose_repo_dir/ui/desktop/out/Goose Local-darwin-arm64/Goose Local.app"
