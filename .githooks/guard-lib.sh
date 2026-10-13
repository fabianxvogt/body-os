# Shared by pre-commit and pre-push (POSIX sh). guard_check <commit-sha|INDEX> prints
# "path  (reason)" for every forbidden path. Names are read NUL-separated with quotePath off, so
# non-ASCII names cannot slip through; matching is case-insensitive.

guard_check() {
  src=$1
  if [ "$src" = INDEX ]; then
    paths=$(git -c core.quotePath=false diff --cached --name-only -z --diff-filter=ACMR | tr '\0' '\n')
  else
    paths=$(git -c core.quotePath=false ls-tree -r -z --name-only "$src" | tr '\0' '\n')
  fi
  printf '%s\n' "$paths" | grep -i -E '^(me|data)/' | sed 's/$/  (private instance or derived data)/'
  printf '%s\n' "$paths" | grep -i -E '(^|/)\.env' | sed 's/$/  (environment\/secret file)/'
  printf '%s\n' "$paths" | grep -i -E '\.jsonl$' | grep -v -i -E '^examples/' |
    while IFS= read -r f; do
      if [ "$src" = INDEX ]; then blob=":$f"; else blob="$src:$f"; fi
      if git show "$blob" 2>/dev/null | grep '"ts"[[:space:]]*:' | grep -q '"type"[[:space:]]*:'; then
        echo "$f  (looks like body-os log data; personal data belongs in me/, synthetic in examples/)"
      fi
    done
}
