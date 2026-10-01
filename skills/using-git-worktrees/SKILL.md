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

Only when Step 1a does not apply (no native worktree tool is available or
allowed). Read `modules/git-worktree-fallback.md` and follow it: directory
selection, the ignore check, creation with the ownership marker, and the
sandbox fallback. Then continue with Step 2.

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
