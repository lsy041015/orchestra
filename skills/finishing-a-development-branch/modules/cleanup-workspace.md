# Step 6: Cleanup Workspace

Part of `orchestra:finishing-a-development-branch`. Read it only for Option 1 or a confirmed discard.

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
