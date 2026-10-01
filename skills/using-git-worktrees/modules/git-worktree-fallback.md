# Step 1b: Git Worktree Fallback

Part of `orchestra:using-git-worktrees`. Read it only when Step 1a found no usable native worktree tool.

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
