---
name: using-git-worktrees
description: "Use when an authorized coding task needs an isolated checkout. Reuse existing isolation; small safe edits do not require a worktree."
---

# Using Git Worktrees

## Overview

Ensure work happens in an isolated workspace. Prefer your platform's native worktree tools. Fall back to manual git worktrees only when no native tool is available.

**Core principle:** Detect existing isolation first. Then use native tools. Then fall back to git. Never fight the harness.

**Announce at start:** "I'm using the using-git-worktrees skill to set up an isolated workspace."

## Step 0: Detect Existing Isolation

**Before creating anything, check if you are already in an isolated workspace.**

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

**Submodule guard:** `GIT_DIR != GIT_COMMON` is also true inside git submodules. Before concluding "already in a worktree," verify you are not in a submodule:

```bash
# If this returns a path, you're in a submodule, not a worktree — treat as normal repo
git rev-parse --show-superproject-working-tree 2>/dev/null
```

**If `GIT_DIR != GIT_COMMON` (and not a submodule):** You are already in a linked worktree. Skip to Step 2 (Project Setup). Do NOT create another worktree.

Report with branch state:
- On a branch: "Already in isolated workspace at `<path>` on branch `<name>`."
- Detached HEAD: "Already in isolated workspace at `<path>` (detached HEAD, externally managed). Branch creation needed at finish time."

**If `GIT_DIR == GIT_COMMON` (or in a submodule):** You are in a normal repo checkout.

Honor the user's workspace preference. Use isolation when concurrent work or
user changes make it useful; small unambiguous edits can stay in place. Follow
the host's authorization rules for a reversible worktree operation. Ask only
when the workspace choice introduces an unresolved conflict or consequential
tradeoff; do not add a routine consent round to an already authorized task.

## Step 1: Create Isolated Workspace

**You have two mechanisms. Try them in this order.**

### 1a. Native Worktree Tools (preferred)

Isolation is appropriate under Step 0. Do you already have a way to create a worktree that this task may use? It might be a tool with a name like `EnterWorktree`, a `/worktree` command, or a `--worktree` flag. If you do, use it and skip to Step 2.

In Claude Code, `EnterWorktree` may be used only when the user or CLAUDE.md
explicitly asks for a worktree. Its default `worktree.baseRef: fresh` branches
from `origin/<default-branch>`, not your local HEAD, so unpushed commits are
missing there. Without such a request, use Step 1b.

Native tools handle directory placement, branch creation, and cleanup automatically. Using `git worktree add` when you have a usable native tool creates phantom state your harness can't see or manage.

Only proceed to Step 1b if no native worktree tool is available or allowed.

### 1b. Git Worktree Fallback

**Only use this if Step 1a does not apply** — no native worktree tool is available or allowed. Create a worktree manually using git.

#### Directory Selection

Resolve one `LOCATION` before running any safety check. Explicit user preference
always beats observed filesystem state.

1. **Check your instructions for a declared worktree directory preference.** If the user has already specified one, use it without asking.

2. **Check for an existing worktree directory at the repository root, regardless of the current directory:**
   ```bash
   repo_root=$(git rev-parse --show-toplevel)
   if [ -d "$repo_root/.worktrees" ]; then
     LOCATION=.worktrees
   elif [ -d "$repo_root/worktrees" ]; then
     LOCATION=worktrees
   else
     LOCATION=.worktrees
   fi
   ```
   If both exist, `.worktrees` wins. The default may not exist yet; that does
   not make it an invalid choice.

3. Treat `LOCATION` as a directory path. Preserve a user-provided trailing
   slash for directory semantics, and when the path has no slash append one
   for the ignore probe. Quote the path in every command.

#### Safety Verification (project-local directories only)

First resolve the repository root and classify the selected location relative
to it. A location outside that root is an external workspace and is not
subject to this project-local ignore probe.

For an internal location, check exactly that location. Do not test `.worktrees`
and `worktrees` as alternatives after `LOCATION` has been chosen:

```bash
# Portable stand-in for GNU `realpath -m` (macOS realpath has no -m): resolve
# the longest existing prefix with `pwd -P` and keep the missing tail as is.
resolve_path() {
  local p=$1 tail=
  while [ "$p" != / ] && [ "${p%/}" != "$p" ]; do p=${p%/}; done
  while [ ! -d "$p" ]; do
    tail="/${p##*/}$tail"
    p=${p%/*}
    [ -n "$p" ] || p=/
  done
  printf '%s%s\n' "$(CDPATH= cd -- "$p" && pwd -P)" "$tail"
}
repo_root=$(resolve_path "$(git rev-parse --show-toplevel)")
# Resolve a relative LOCATION against repo_root, then append / only for this
# directory probe. The selected directory need not exist yet.
case "$LOCATION" in
  /*|[A-Za-z]:[\\/]*) selected="$LOCATION" ;;  # includes Windows drive paths
  *) selected="$repo_root/$LOCATION" ;;
esac
selected=$(resolve_path "$selected")
case "$selected" in
  "$repo_root"|"$repo_root"/*)
    probe="$selected"
    case "$probe" in
      */) ;;
      *) probe="$probe/" ;;
    esac
    git -C "$repo_root" check-ignore -q -- "$probe"
    ;;
  *)
    echo "Selected external worktree location: $selected"
    ;;
esac
```

The `--` and quotes are required for spaces and option-like names. A
directory-only pattern such as `.worktrees/` must match the same `probe`,
including when the directory is not present yet. If the selected location is
not ignored, add that exact directory pattern (relative to `repo_root`) to
`.gitignore`, tell the user you changed that tracked file, and rerun the same
check. Follow the repository's normal commit policy; do not create an
arbitrary safety-only commit just to satisfy this check.

**Why critical:** Prevents accidentally committing worktree contents to repository.

#### Create the Worktree

```bash
# Use the exact normalized path that passed the safety check. Do not rebuild it
# from LOCATION, which could resolve somewhere else after changing directory.
# (Not named `path`: zsh ties that name to PATH.)
wt_path="$selected/$BRANCH_NAME"

# Stop at the first failure: marking a worktree this step did not create lets
# cleanup delete someone else's work.
git -C "$repo_root" worktree add -b "$BRANCH_NAME" -- "$wt_path" &&
  cd "$wt_path" &&
  git_dir=$(CDPATH= cd -- "$(git rev-parse --git-dir)" && pwd -P) &&
  pwd -P > "$git_dir/orchestra-owned-worktree"
```

If `git worktree add` fails because the branch or path already exists, stop
and report it; do not reuse or mark the existing directory. If only the marker
write fails (a sandbox may protect `.git`), report that the worktree exists
but finishing-a-development-branch will not remove it automatically.

**Sandbox fallback:** If `git worktree add` fails with a permission error (sandbox denial), tell the user the sandbox blocked worktree creation and you're working in the current directory instead. Then run setup and baseline tests in place.

## Step 2: Project Setup

Auto-detect and run appropriate setup:

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python: only into an active virtual environment, never the global interpreter
if [ -f requirements.txt ] && [ -n "${VIRTUAL_ENV:-}" ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

With `requirements.txt` and no active virtual environment, ask before
installing anything into the global Python interpreter.

## Step 3: Verify Clean Baseline

Run tests to ensure workspace starts clean:

```bash
# Use project-appropriate command
npm test / cargo test / pytest / go test ./...
```

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

### Report

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

## Quick Reference

| Situation | Action |
|-----------|--------|
| Already in linked worktree | Skip creation (Step 0) |
| In a submodule | Treat as normal repo (Step 0 guard) |
| Native worktree tool available and allowed | Use it (Step 1a) |
| No usable native tool | Git worktree fallback (Step 1b) |
| Branch or path already exists | Stop and report; never mark it |
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check instruction file, then default `.worktrees/` |
| Directory not ignored | Add the selected directory pattern and follow normal repository commit policy |
| Permission error on create | Sandbox fallback, work in place |
| Tests fail during baseline | Report failures + ask |
| No package.json/Cargo.toml | Skip dependency install |

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'm obviously not in a worktree — no need to check" | Run Step 0. Harness-created isolation and submodules both fool eyeballing; the detection commands settle it. |
| "`git worktree add` is quicker than hunting for a native tool" | A native tool you may use owns placement, branching, and cleanup. Bypassing it creates phantom state your harness can't see or manage. In Claude Code that means `EnterWorktree` after an explicit worktree request; otherwise the git fallback is the right path. |
| "The worktree directory is surely ignored already" | Run `git check-ignore`. An unignored worktree directory commits the whole tree into the repo. |
| "Any directory name works" | Explicit instructions beat an existing project-local directory, which beats the `.worktrees/` default. |
| "The workspace is fresh — baseline tests can wait" | A dirty baseline makes every later failure ambiguous. Run the tests now; proceeding past failures is your human partner's call. |
