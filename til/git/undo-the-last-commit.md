---
tags: undo, reset
---

# Four ways to undo the last commit

Which one you want depends on what you would like to keep.

```bash
git commit --amend --no-edit     # keep the commit, fold in staged changes
git reset --soft HEAD~1          # remove the commit, keep changes staged
git reset HEAD~1                 # remove the commit, keep changes unstaged
git reset --hard HEAD~1          # remove the commit and the changes
```

`--soft` is the one I reach for most: it puts the tree back exactly as it was
just before `git commit`, so I can restage and split the work up differently.

## If the commit is already pushed

Do not rewrite shared history — make a new commit that reverses it:

```bash
git revert HEAD
```

## If you --hard reset something you needed

The commit is still in the reflog for a couple of weeks:

```bash
git reflog                  # find the sha you were on
git reset --hard <sha>
```

`git reflog` only records where *your* HEAD has been, so it cannot recover work
that was never committed. Uncommitted changes destroyed by `--hard` are gone.
