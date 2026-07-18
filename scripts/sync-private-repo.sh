#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# Sync full application source + docs to private GitHub:
#   github.com/markusvankempen/slack-wxo-mcp-gateway-dev
#
# Never pushes secrets (.env, config.yaml, .run/, tokens).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${PUBLISH_DIR:-/tmp/slack-wxo-mcp-gateway-dev}"
STAGING="${DEST}.staging"
REPO="markusvankempen/slack-wxo-mcp-gateway-dev"
BRANCH="${PUBLISH_BRANCH:-main}"

echo "==> Source: $ROOT (code + docs)"
echo "==> Dest:   $DEST"
echo "==> Repo:   $REPO (private)"

if command -v gh >/dev/null 2>&1; then
  gh auth switch --user markusvankempen 2>/dev/null || true
fi

rm -rf "$STAGING"
mkdir -p "$STAGING"

# Full tree minus secrets / junk (include before exclude — first match wins)
rsync -a \
  --include '.env.example' \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'config.yaml' \
  --exclude '.run/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '.deps-ok' \
  --exclude 'node_modules/' \
  --exclude '*.tgz' \
  --exclude '*.log' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  --exclude '.mcpregistry*' \
  --exclude '.npmrc' \
  "$ROOT/" "$STAGING/"

cat > "$STAGING/.gitignore" <<'EOF'
.env
.env.*
!.env.example
config.yaml
.run/
__pycache__/
*.pyc
.DS_Store
.deps-ok
node_modules/
*.tgz
*.log
.venv/
venv/
.pytest_cache/
.mypy_cache/
.mcpregistry*
.npmrc
EOF

# Safety: never ship secrets even if they slipped past rsync
rm -f "$STAGING/.env" "$STAGING/config.yaml"
rm -f "$STAGING"/.mcpregistry* "$STAGING/.npmrc"
rm -rf "$STAGING/.run"

if [[ -f "$STAGING/.env" ]] || [[ -f "$STAGING/config.yaml" ]] || [[ -d "$STAGING/.run" ]] \
  || compgen -G "$STAGING/.mcpregistry*" >/dev/null; then
  echo "ERROR: secrets still present in staging — aborting" >&2
  ls -la "$STAGING"/.env "$STAGING"/config.yaml "$STAGING"/.mcpregistry* 2>/dev/null || true
  exit 1
fi

rm -rf "$DEST"

if gh repo view "$REPO" >/dev/null 2>&1; then
  git clone "https://github.com/${REPO}.git" "$DEST"
  cd "$DEST"
  find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  cp -a "$STAGING"/. .
else
  mkdir -p "$DEST"
  cp -a "$STAGING"/. "$DEST/"
  cd "$DEST"
  git init -b "$BRANCH"
fi

rm -rf "$STAGING"

git add -A
if git diff --cached --quiet; then
  echo "Nothing to commit."
else
  git commit -m "$(cat <<'EOF'
Publish code + docs to private slack-wxo-mcp-gateway-dev.

EOF
)"
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$REPO" \
    --private \
    --description "Private: Slack ↔ watsonx Orchestrate MCP gateway (full source + docs)" \
    --homepage "https://markusvankempen.github.io/" \
    --source . \
    --remote origin \
    --push
  echo "==> Created and pushed https://github.com/${REPO}"
else
  git push -u origin "HEAD:${BRANCH}"
  gh repo edit "$REPO" \
    --description "Private: Slack ↔ watsonx Orchestrate MCP gateway (full source + docs)" \
    --homepage "https://markusvankempen.github.io/" \
    >/dev/null || true
  echo "==> Pushed https://github.com/${REPO}"
fi

gh repo view "$REPO" --json name,visibility,url,description
