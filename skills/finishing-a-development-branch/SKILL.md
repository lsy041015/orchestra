---
name: finishing-a-development-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work
---

# Finishing a Development Branch

## Overview

**Core principle:** Verify tests → Detect environment → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the finishing-a-development-branch skill to complete this work."

## Step 1: Verify Tests

Apply **orchestra:verification-before-completion** to the
state you are about to integrate. Inspect matching evidence for the project's
required checks, including its full suite when required. Run only missing,
invalidated, or still-unverified checks.

**If tests fail**, report the failures and stop — the menu comes after a green suite:

```
Tests failing (<N> failures). Must fix before completing:

[Show failures]
```

**If tests pass:** check for uncommitted work, then continue to Step 2.

Workers may leave reviewed changes uncommitted; Codex workers cannot commit
at all. Run `git status --porcelain`. If it lists reviewed task changes, show
them and ask whether to commit them to the feature branch before choosing an
option. Merging or pushing a branch leaves uncommitted work behind.

## Step 2: Detect Environment

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
# Capture now, while still inside the workspace — Step 5 changes directory
# before cleanup (Step 6) needs this value
WORKTREE_PATH=$(git rev-parse --show-toplevel)
```

This determines which menu to show and how cleanup works:

| State | Menu | Cleanup |
|-------|------|---------|
| `GIT_DIR == GIT_COMMON` (normal repo) | Standard 3 options | No worktree to clean up |
| `GIT_DIR != GIT_COMMON`, named branch | Standard 3 options | Provenance-based (see Step 6) |
| `GIT_DIR != GIT_COMMON`, detached HEAD | Reduced 2 options (no merge) | Externally managed — leave in place |

## Step 3: Determine Base Branch

The base branch is whatever this work forked from — usually named in the
plan, the conversation, or the branch's upstream. If it is not already
known, ask: "This branch split from <your best guess> - is that correct?"
Confirm before merging: merging into the wrong base is expensive to undo.

## Step 4: Present Options

**Normal repo and named-branch worktree — present exactly these 3 options:**

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally (then remove this worktree and branch)
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)

Which option?
```

**Detached HEAD — present exactly these 2 options:**

```
Implementation complete. You're on a detached HEAD (externally managed workspace).

1. Push as new branch and create a Pull Request
2. Keep as-is (I'll handle it later)

Which option?
```

Present the menu exactly as written — concise, with every option coming
from the list above. Discarding the work happens only in response to your
human partner explicitly asking for it (see "If your human partner asks to
discard the work" below). Wait for their answer; the integration decision
is theirs.

## Step 5: Execute Choice

### Option 1: Merge Locally

```bash
# Main worktree for CWD safety: the first `git worktree list` entry. In a bare
# repository that entry has no work tree, so the checkout below fails there.
MAIN_ROOT=$(git worktree list --porcelain | sed -n '1s/^worktree //p')

# Merge first — verify success before removing anything. Stop at the first
# failure: after a failed checkout, merge would land on the current branch.
[ -n "$MAIN_ROOT" ] && cd "$MAIN_ROOT" &&
  git checkout <base-branch> &&
  if git rev-parse --verify --quiet '@{upstream}' >/dev/null; then git pull --ff-only; fi &&
  git merge <feature-branch>

# Verify tests on merged result
<test command>
```

If checkout, pull, or merge fails, stop and report it; never run the merge from
another branch. If tests fail on the merged result: stop, leave the worktree
and branch in place, and investigate — nothing has been pushed, so the merge
is local and recoverable.

Once the merged result is green: clean up the worktree (Step 6). Delete
the branch only if that worktree was removed; a preserved worktree keeps
its branch:

```bash
git branch -d <feature-branch>
```

### Option 2: Push and Create PR

```bash
git push -u origin <feature-branch>
# From a detached HEAD, name the new branch on the remote:
# git push origin HEAD:refs/heads/<new-branch>
```

Then create the pull/merge request against <base-branch> with the forge's
tooling — its CLI if one is available, or the creation URL most forges
print when you push — following the repo's PR template and conventions if
present, and report the URL to your human partner.

Keep the worktree — your human partner iterates on PR feedback there.

### Option 3: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."

### If your human partner asks to discard the work

This path exists only as a response to an explicit request to throw the
work away. Confirm first:

```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for that exact confirmation. When it arrives:

```bash
MAIN_ROOT=$(git worktree list --porcelain | sed -n '1s/^worktree //p')
[ -n "$MAIN_ROOT" ] && cd "$MAIN_ROOT"
```

Then clean up the worktree (Step 6). Force-delete the branch only if
that worktree was removed:

```bash
git branch -D <feature-branch>
```

## Step 6: Cleanup Workspace

**Runs for Option 1 and confirmed discards.** Options 2 and 3 always
preserve the worktree. Both callers have already changed directory to the
main repo root — worktree removal must run from outside the worktree.
Shell variables do not survive between tool calls, so use the results of
Step 2 as you recorded them, not as fresh commands from the new directory.

**If Step 2 found `GIT_DIR == GIT_COMMON`:** Normal repo, no worktree to clean up. Done.

**If the Git administrative directory has an Orchestra ownership marker matching
the physical worktree path:** Orchestra created this worktree and may clean it up.
Write the worktree path from Step 2 into the first line:

```bash
WORKTREE_PATH="<worktree path from Step 2>"
wt_git_dir=$(git -C "$WORKTREE_PATH" rev-parse --absolute-git-dir)
if [ ! -f "$wt_git_dir/orchestra-owned-worktree" ] ||
   [ "$(cat "$wt_git_dir/orchestra-owned-worktree")" != "$(CDPATH= cd -- "$WORKTREE_PATH" && pwd -P)" ]; then
  echo "Worktree was not created by Orchestra; leaving it in place."
else
  # Orchestra's records (ledger, reports, mockups) are ignored too: keep them.
  main_root=$(git -C "$WORKTREE_PATH" worktree list --porcelain | sed -n '1s/^worktree //p')
  if [ -d "$WORKTREE_PATH/.orchestra" ] && [ -n "$main_root" ]; then
    archive="$main_root/.orchestra/archive"
    mkdir -p "$archive" && { [ -e "$archive/.gitignore" ] || printf '*\n' > "$archive/.gitignore"; } &&
      mv "$WORKTREE_PATH/.orchestra" "$archive/$(basename "$WORKTREE_PATH")-$(date +%Y%m%d-%H%M%S)" &&
      echo "Moved Orchestra records to $archive/"
  fi
  ignored=$(git -C "$WORKTREE_PATH" status --porcelain --ignored | grep '^!!' || true)
  if [ -n "$ignored" ]; then
    # `git worktree remove` deletes ignored files (.env, local databases) silently.
    printf 'Ignored files would be deleted with the worktree:\n%s\n' "$ignored"
  else
    # No `git worktree prune`: it also drops other worktrees whose folders are
    # only temporarily missing. `remove` already clears its own registration.
    git worktree remove "$WORKTREE_PATH"
  fi
fi
```

Orchestra's own records (`.orchestra/`) move to
`<main checkout>/.orchestra/archive/<worktree>-<time>/` first, so they never
block cleanup. **If other ignored files are listed:** show them and ask
whether to move them into the main checkout, delete them with the worktree,
or keep the worktree.

**If removal is refused** (`contains modified or untracked files`): the
worktree holds files that exist nowhere else — uncommitted plans, notes,
or scratch work. Never `--force` on your own initiative. Show your human
partner what is at stake and ask:

```bash
git -C "$WORKTREE_PATH" status --porcelain -uall
```

```
Worktree removal refused — these files were never committed:

<file list>

1. Commit them to <branch> before cleanup
2. Move them into <main repo root>
3. Delete them (unrecoverable)

Which?
```

Carry out the choice, then remove the worktree.

**Otherwise:** The host environment owns this workspace — leave it and
its branch in place. If your platform provides a workspace-exit tool, use it
only in a mode that keeps the worktree (Claude Code: `ExitWorktree` with
`action: "keep"`; `"remove"` deletes the worktree and its branch).

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | yes | - | - | yes |
| 2. Create PR | - | yes | yes | - |
| 3. Keep as-is | - | - | yes | - |
| Discard (explicit request only) | - | - | - | yes (force) |

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Tests passed earlier this session" | Earlier evidence is reusable only when it meets verification-before-completion's state and coverage rules. Verify any changed integration result. |
| "They obviously want it merged" | Integration is your human partner's decision. Present the menu and wait. |
| "They seem done with this feature — I'll offer to discard it" | The menu is complete as written. Discard happens only when your human partner asks for it in so many words. |
| "'Yeah, get rid of it' counts as confirmation" | Only the typed word `discard` authorizes deletion. |
| "The PR is up, so the worktree is clutter now" | PR feedback gets fixed in that worktree. It stays until the work lands. |
| "This other worktree looks stale — I'll clean it too" | Clean up only worktrees with a matching Orchestra ownership marker. Directory names do not prove ownership. |
| "Removal refused — `--force` is just finishing the cleanup" | The refusal means files exist only in that worktree. `--force` destroys them permanently. Show your human partner and ask. |
| "The merged-result failure is probably flaky" | A failing merged result stops everything. Branch and worktree stay put while you investigate. |
| "The base branch is obviously main" | Confirm the fork point or ask. Merging into the wrong base is expensive to undo. |
| "The push was rejected — force-push will fix it" | A rejected push means the remote moved. Investigate; force-push only on your human partner's explicit request. |
