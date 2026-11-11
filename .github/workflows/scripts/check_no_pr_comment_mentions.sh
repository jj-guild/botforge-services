#!/usr/bin/env bash
# Guard: no PR/issue comment may render a @login mention (they ping the
# rostered human on every command — the spam reported after #358: the
# ack comments were fixed alias-first, then the tracking tables
# reintroduced `(@${commenter})`).
#
# Convention (CONVENTIONS.md): comments name the requestor alias-first,
# with the BARE login as fallback — never a @mention. The only allowed
# `@${...}` occurrences in the workflows are roster lookups against
# CONTRIBUTORS.md (`| @login |` row patterns — grep inputs, never
# rendered comment text) and non-comment strings like image/branch
# labels (`${alias}@${sha}`). A rendered mention in a comment body
# always shows up as `(@${...})` or `**@${...}` — those fail here.
#
# Usage:
#   scripts/check_no_pr_comment_mentions.sh          (from the repo root)
#
# Run by CI (Lint workflows job).

set -euo pipefail

python3 - "$(pwd)" <<'PYEOF'
import re
import sys
from pathlib import Path

# a rendered @mention inside a comment body: parenthesized or bold
MENTION_RE = re.compile(r"\(@\$\{|\*\*@\$\{")
root = Path(sys.argv[1])
failed = False
checked = 0

for workflow in sorted((root / ".github" / "workflows").glob("*.yml")):
    checked += 1
    for lineno, line in enumerate(workflow.read_text().splitlines(), start=1):
        if MENTION_RE.search(line):
            print(
                f"::error file={workflow.name},line={lineno}::"
                "PR/issue comments must never render a @login mention — name the "
                "requestor alias-first with the bare login (CONVENTIONS.md; "
                "see #358). Roster lookups (`| @login |` in CONTRIBUTORS.md) are "
                "grep inputs, not comment text, and stay allowed",
                file=sys.stderr,
            )
            failed = True

if checked == 0:
    print("::error::no workflow files found — check the script's path", file=sys.stderr)
    sys.exit(1)
if failed:
    sys.exit(1)
print(f"NO-PR-COMMENT-MENTION CHECK OK ({checked} workflows scanned)")
PYEOF
