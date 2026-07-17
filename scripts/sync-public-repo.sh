#!/usr/bin/env bash
# Sync a clean publish tree and push to github.com/markusvankempen/slack-wxo-mcp-gateway
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${PUBLISH_DIR:-/tmp/slack-wxo-mcp-gateway-publish}"
REPO="markusvankempen/slack-wxo-mcp-gateway"
BRANCH="${PUBLISH_BRANCH:-main}"

echo "==> Source: $ROOT"
echo "==> Dest:   $DEST"

rm -rf "$DEST"
mkdir -p "$DEST"

rsync -a \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude '!.env.example' \
  --exclude 'config.yaml' \
  --exclude '.run/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '.deps-ok' \
  --exclude 'node_modules/' \
  --exclude '*.tgz' \
  --exclude '.git/' \
  "$ROOT/" "$DEST/"

# Ensure .env.example is present (rsync exclude of .env.* may drop it)
cp -f "$ROOT/.env.example" "$DEST/.env.example"

# Public gitignore (no secrets)
cat > "$DEST/.gitignore" <<'EOF'
.env
config.yaml
.run/
__pycache__/
*.pyc
.DS_Store
.deps-ok
node_modules/
*.tgz
*.log
EOF

cd "$DEST"

if [[ ! -d .git ]]; then
  git init -b "$BRANCH"
fi

git add -A
if git diff --cached --quiet; then
  echo "Nothing to commit."
else
  git commit -m "$(cat <<'EOF'
Publish Slack ↔ WxO MCP gateway docs and npm package source.

EOF
)"
fi

# Prefer markusvankempen account for this public repo
if command -v gh >/dev/null 2>&1; then
  gh auth switch --user markusvankempen 2>/dev/null || true
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  if gh repo view "$REPO" >/dev/null 2>&1; then
    git remote add origin "https://github.com/${REPO}.git"
  else
    gh repo create "$REPO" \
      --public \
      --description "Slack ↔ watsonx Orchestrate MCP gateway — multi-channel routing, poller, admin UI, streamable HTTP /mcp" \
      --homepage "https://github.com/${REPO}" \
      --source . \
      --remote origin \
      --push
    echo "==> Created and pushed https://github.com/${REPO}"
    exit 0
  fi
fi

git push -u origin "$BRANCH"
echo "==> Pushed https://github.com/${REPO}"
