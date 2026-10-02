# Option 1: Merge locally

Part of `orchestra:finishing-a-development-branch`. Read it only when the user chose Option 1.

```bash
# Main worktree for CWD safety: the first `git worktree list` entry. In a bare
# repository that entry has no work tree, so the checkout below fails there.
MAIN_ROOT=$(git worktree list --porcelain | sed -n '1s/^worktree //p')

# Merge first, then verify tests on the merged result — before removing
# anything. Stop at the first failure: after a failed checkout, merge would
# land on the current branch; after a failed merge, tests would pass on the
# unmerged base and the block would still exit 0.
[ -n "$MAIN_ROOT" ] && cd "$MAIN_ROOT" &&
  [ -z "$(git status --porcelain --untracked-files=no)" ] &&
  git checkout <base-branch> &&
  if git rev-parse --verify --quiet '@{upstream}' >/dev/null; then git pull --ff-only; fi &&
  git merge <feature-branch> &&
  <test command>
```

If the main checkout has uncommitted changes to tracked files, the block stops
before the checkout: it would switch the user's branch and merge with their
work in place. Report it and ask. If checkout, pull, or merge fails, stop and
report it; never run the merge from another branch. If tests fail on the merged result: stop, leave the worktree
and branch in place, and investigate — nothing has been pushed, so the merge
is local and recoverable.

Once the merged result is green: clean up the worktree (Step 6). Delete
the branch only if that worktree was removed; a preserved worktree keeps
its branch:

```bash
git branch -d <feature-branch>
```
