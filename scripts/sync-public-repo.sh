#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${PUBLISH_DIR:-/tmp/slack-wxo-mcp-gateway-publish}"
STAGING="${DEST}.staging"
REPO="markusvankempen/slack-wxo-mcp-gateway"
BRANCH="${PUBLISH_BRANCH:-main}"

DOC_FILES=(
  README.md
  USE_CASES.md
  SETUP.md
  PUBLISH.md
  LICENSE
  config.example.yaml
  .env.example
  agent.yaml
  package.json
)

# Example agent YAMLs + path-specific docs (not the Python gateway)
DOC_DIRS=(
  agents
  docs
  examples
  .github
)

echo "==> Source: $ROOT (docs only)"
echo "==> Dest:   $DEST"

if command -v gh >/dev/null 2>&1; then
  gh auth switch --user markusvankempen 2>/dev/null || true
fi

rm -rf "$STAGING"
mkdir -p "$STAGING"
for f in "${DOC_FILES[@]}"; do
  if [[ ! -f "$ROOT/$f" ]]; then
    echo "Missing required doc file: $f" >&2
    exit 1
  fi
  cp -f "$ROOT/$f" "$STAGING/$f"
done

for d in "${DOC_DIRS[@]}"; do
  if [[ -d "$ROOT/$d" ]]; then
    # Preserve subdirectory layout (e.g. docs/local-ngrok, docs/code-engine)
    # only yaml/md — never copy secrets or binaries
    while IFS= read -r -d '' f; do
      rel="${f#"$ROOT/"}"
      mkdir -p "$STAGING/$(dirname "$rel")"
      cp -f "$f" "$STAGING/$rel"
    done < <(find "$ROOT/$d" -type f \( -name '*.yaml' -o -name '*.yml' -o -name '*.md' -o -name '*.json' \) -print0 2>/dev/null)
  fi
done

# Scripts useful for docs consumers (modes A–D)
mkdir -p "$STAGING/scripts"
for s in apply-github-metadata.sh run.sh sync-public-repo.sh; do
  [[ -f "$ROOT/scripts/$s" ]] && cp -f "$ROOT/scripts/$s" "$STAGING/scripts/"
done

cat > "$STAGING/.gitignore" <<'EOF'
.env
config.yaml
.run/
__pycache__/
*.pyc
.DS_Store
node_modules/
EOF

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
Publish documentation only (no application source).

EOF
)"
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$REPO" \
    --public \
    --description "Documentation for Slack ↔ watsonx Orchestrate MCP gateway" \
    --homepage "https://github.com/${REPO}" \
    --source . \
    --remote origin \
    --push
  echo "==> Created and pushed https://github.com/${REPO}"
  exit 0
fi

git push -u origin "HEAD:${BRANCH}"

# Keep GitHub description aligned with docs-only intent
gh repo edit "$REPO" \
  --description "Documentation for Slack ↔ watsonx Orchestrate MCP gateway" \
  --homepage "https://github.com/${REPO}" \
  >/dev/null || true

echo "==> Pushed docs-only https://github.com/${REPO}"
