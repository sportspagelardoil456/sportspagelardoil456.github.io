#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# Apply GitHub description, homepage, and topic tags for discoverability.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
META_FILE="${REPO_ROOT}/.github/repository-metadata.json"

command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI required" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 required" >&2; exit 1; }
[[ -f "$META_FILE" ]] || { echo "ERROR: missing $META_FILE" >&2; exit 1; }

gh auth switch --user markusvankempen 2>/dev/null || true

python3 - "$META_FILE" <<'PY'
import json, subprocess, sys

with open(sys.argv[1]) as f:
    cfg = json.load(f)["public"]

repo = cfg["repo"]
description = cfg["description"]
homepage = cfg.get("homepage") or ""
topics = cfg["topics"]

print(f"==> {repo}")
print(f"    description: {description[:80]}…")
cmd = ["gh", "repo", "edit", repo, "--description", description]
if homepage:
    cmd += ["--homepage", homepage]
subprocess.run(cmd, check=True)

# GitHub allows up to 20 topics
topics = topics[:20]
payload = json.dumps({"names": topics})
subprocess.run(
    [
        "gh", "api", "--method", "PUT",
        f"repos/{repo}/topics",
        "--input", "-",
        "-H", "Accept: application/vnd.github.mercy-preview+json",
    ],
    input=payload,
    text=True,
    check=True,
)
print(f"    topics ({len(topics)}):")
for t in topics:
    print(f"      · {t}")
print(f"Done: https://github.com/{repo}")
PY
