#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# Sync documentation + package metadata only (NO application source) to:
#   github.com/markusvankempen/slack-wxo-mcp-gateway
#
# Runnable app source stays private (slack-wxo-mcp-gateway-dev) and on npm.
# Never pushes .env, config.yaml, .run/, or Python/JS application source.
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
  server.json
)

DOC_DIRS=(
  agents
  docs
  examples
  .github
)

echo "==> Source: $ROOT (docs + metadata only — no app source)"
echo "==> Dest:   $DEST"
echo "==> Repo:   $REPO (public)"

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
    while IFS= read -r -d '' f; do
      rel="${f#"$ROOT/"}"
      mkdir -p "$STAGING/$(dirname "$rel")"
      cp -f "$f" "$STAGING/$rel"
    done < <(find "$ROOT/$d" -type f \( -name '*.yaml' -o -name '*.yml' -o -name '*.md' -o -name '*.json' \) -print0 2>/dev/null)
  fi
done

mkdir -p "$STAGING/scripts"
for s in apply-github-metadata.sh sync-public-repo.sh; do
  [[ -f "$ROOT/scripts/$s" ]] && cp -f "$ROOT/scripts/$s" "$STAGING/scripts/"
done

# Public package.json: identity only (no bin / files that imply clone-and-run)
STAGING="$STAGING" node <<'NODE'
const fs = require("fs");
const path = require("path");
const staging = process.env.STAGING;
const pkgPath = path.join(staging, "package.json");
const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
delete pkg.bin;
delete pkg.files;
delete pkg.scripts;
pkg.scripts = {
  "github:metadata": "bash scripts/apply-github-metadata.sh",
  "sync:public": "bash scripts/sync-public-repo.sh",
};
pkg.private = true; // prevent accidental npm publish from this docs tree
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
console.log("package.json → docs metadata only (no bin/files)");
NODE

cat > "$STAGING/.gitignore" <<'EOF'
.env
.env.*
!.env.example
config.yaml
.run/
__pycache__/
*.pyc
.DS_Store
node_modules/
*.py
bin/
*.tgz
.mcpregistry*
.npmrc
Dockerfile
requirements.txt
ui.html
EOF

rm -rf "$STAGING"/*.py "$STAGING"/bin "$STAGING"/__pycache__ 2>/dev/null || true
rm -f "$STAGING"/Dockerfile "$STAGING"/requirements.txt \
  "$STAGING"/deploy_*.sh "$STAGING"/test_*.sh "$STAGING"/stop.sh \
  "$STAGING"/ui.html "$STAGING"/.npmignore "$STAGING"/.dockerignore 2>/dev/null || true

if find "$STAGING" -name '*.py' -print -quit | grep -q .; then
  echo "ERROR: Python source found in public staging — aborting" >&2
  find "$STAGING" -name '*.py'
  exit 1
fi
if [[ -d "$STAGING/bin" ]] || [[ -f "$STAGING/server.py" ]] || [[ -f "$STAGING/ui.html" ]]; then
  echo "ERROR: application source must not be in public docs repo" >&2
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
Publish documentation and package metadata only (no application source).

EOF
)"
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$REPO" \
    --public \
    --description "Docs for Slack↔WxO MCP — install via npm @markusvankempen/slack-wxo-mcp-gateway. https://markusvankempen.github.io/" \
    --homepage "https://markusvankempen.github.io/" \
    --source . \
    --remote origin \
    --push
  echo "==> Created and pushed https://github.com/${REPO}"
  exit 0
fi

git push -u origin "HEAD:${BRANCH}"

if [[ -x "$ROOT/scripts/apply-github-metadata.sh" ]]; then
  bash "$ROOT/scripts/apply-github-metadata.sh" >/dev/null 2>&1 || true
else
  gh repo edit "$REPO" \
    --description "Docs for Slack↔WxO MCP — install via npm @markusvankempen/slack-wxo-mcp-gateway. https://markusvankempen.github.io/" \
    --homepage "https://markusvankempen.github.io/" \
    >/dev/null || true
fi

echo "==> Pushed docs-only https://github.com/${REPO}"
