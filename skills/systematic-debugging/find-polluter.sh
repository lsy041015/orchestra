#!/usr/bin/env bash
# Bisection script to find which test creates unwanted files/state
# Usage: ./find-polluter.sh <file_or_dir_to_check> <test_pattern>
# Example: ./find-polluter.sh '.git' 'src/**/*.test.ts'

set -e

if [ $# -ne 2 ]; then
  echo "Usage: $0 <file_to_check> <test_pattern>"
  echo "Example: $0 '.git' 'src/**/*.test.ts'"
  exit 1
fi

POLLUTION_CHECK="$1"
TEST_PATTERN="$2"

echo "🔍 Searching for test that creates: $POLLUTION_CHECK"
echo "Test pattern: $TEST_PATTERN"
echo ""

# Refuse to report "clean" when nothing could be checked.
if [ -e "$POLLUTION_CHECK" ]; then
  echo "❌ $POLLUTION_CHECK already exists. Remove it, then rerun."
  exit 2
fi
if ! node -e "process.exit(require('./package.json').scripts?.test ? 0 : 1)" 2>/dev/null; then
  echo "❌ No package.json with a \"test\" script here; this script runs npm test <file>."
  exit 2
fi

# Get list of test files (find . emits ./-prefixed paths, so accept the
# pattern written with or without a leading ./)
TEST_PATTERN="${TEST_PATTERN#./}"
# find -path can't match '**/' against zero directory levels, so a pattern
# like src/**/*.test.ts would skip src/top.test.ts; also try the pattern
# with '**/' collapsed to cover files directly under the base directory.
TEST_FILES=$(find . \( -name node_modules -o -name .git \) -prune -o \
  \( -path "./$TEST_PATTERN" -o -path "./${TEST_PATTERN//\*\*\//}" \) -print | sort -u)
if [ -z "$TEST_FILES" ]; then
  TOTAL=0
else
  TOTAL=$(printf '%s\n' "$TEST_FILES" | wc -l | tr -d ' ')
fi

echo "Found $TOTAL test files"
echo ""

COUNT=0
# One file per line, so names with spaces stay whole.
while IFS= read -r TEST_FILE; do
  [ -n "$TEST_FILE" ] || continue
  COUNT=$((COUNT + 1))

  echo "[$COUNT/$TOTAL] Testing: $TEST_FILE"

  # Run the test; stdin is the file list, which a test must not read.
  npm test "$TEST_FILE" < /dev/null > /dev/null 2>&1 || true

  # Check if pollution appeared
  if [ -e "$POLLUTION_CHECK" ]; then
    echo ""
    echo "🎯 FOUND POLLUTER!"
    echo "   Test: $TEST_FILE"
    echo "   Created: $POLLUTION_CHECK"
    echo ""
    echo "Pollution details:"
    ls -la "$POLLUTION_CHECK"
    echo ""
    echo "To investigate:"
    echo "  npm test \"$TEST_FILE\"    # Run just this test"
    echo "  cat \"$TEST_FILE\"         # Review test code"
    exit 1
  fi
done <<< "$TEST_FILES"

echo ""
echo "✅ No polluter found - all tests clean!"
exit 0
