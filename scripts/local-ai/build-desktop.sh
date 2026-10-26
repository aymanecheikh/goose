#!/usr/bin/env bash
set -euo pipefail

goose_repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$goose_repo_dir"
source bin/activate-hermit
UV_PROJECT_ENVIRONMENT="$HOME/.local/share/goose-tools/knowledge-venv" \
  /opt/homebrew/bin/uv sync --project extensions/local-knowledge --frozen --no-dev
knowledge_install_dir="$HOME/.local/share/goose-tools/knowledge-server"
mkdir -p "$knowledge_install_dir"
for knowledge_file in knowledge.py server.py; do
  cp "extensions/local-knowledge/$knowledge_file" "$knowledge_install_dir/$knowledge_file.pending"
  mv -f "$knowledge_install_dir/$knowledge_file.pending" "$knowledge_install_dir/$knowledge_file"
done
node scripts/local-ai/prepare-engine.mjs
pnpm --dir ui install --frozen-lockfile
pnpm --dir ui/desktop run package
codesign --force --deep --sign - --entitlements ui/desktop/entitlements.plist \
  "ui/desktop/out/Goose Local-darwin-arm64/Goose Local.app"
printf 'Built: %s\n' "$goose_repo_dir/ui/desktop/out/Goose Local-darwin-arm64/Goose Local.app"
