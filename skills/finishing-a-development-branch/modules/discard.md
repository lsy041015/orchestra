# Discard the work

Part of `orchestra:finishing-a-development-branch`. Read it only when the user explicitly asked to discard the work.

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
