#!/bin/sh
# Refuse commits that add or change personal context.
#
#   tools/hooks/check-private.sh <git rev-list arguments>
#   tools/hooks/check-private.sh origin/main..HEAD
#   tools/hooks/check-private.sh <sha> --not --remotes
#
# Checks every commit in the range, not just the last one, so a file committed and
# then removed in a later commit is still caught. A commit that only deletes such a
# file is allowed (that's the fix). The paths are in tools/hooks/private-paths.
# Exit 0 when clean, 1 when a commit holds personal context.
HERE="$(cd "$(dirname "$0")" && pwd)"
PATTERN="$(grep -v '^#' "$HERE/private-paths" | grep -v '^[[:space:]]*$' | head -1)"
[ -n "$PATTERN" ] || { echo "check-private: no pattern in $HERE/private-paths" >&2; exit 2; }
COMMITS="$(git rev-list "$@")" || { echo "check-private: couldn't list commits for: $*" >&2; exit 2; }
status=0
for c in $COMMITS; do
  bad="$(git diff-tree --no-commit-id --name-only -r --root --diff-filter=AMRC "$c" | grep -E "$PATTERN" | head -5)"
  if [ -n "$bad" ]; then
    echo "Commit $(git log -1 --format='%h %s' "$c") holds personal context, which belongs only in me/ (ignored):"
    echo "$bad" | sed 's/^/  /'
    status=1
  fi
done
[ "$status" -eq 0 ] || echo "Rewrite those commits without the files (for example git rebase, then git rm --cached <path>) and push again."
exit $status
