---
tags: history, recovery
---

# Find and restore a file deleted long ago

Find the commit that removed it, even if you only half remember the name:

```bash
git log --diff-filter=D --name-only --oneline -- '**/config*'
```

`--diff-filter=D` restricts the log to commits where a matching path was
deleted, and `--name-only` prints the paths so you can confirm the exact
spelling.

Then restore the file from the commit *before* the deletion — that is what the
`^` suffix means:

```bash
git restore --source=<sha>^ -- path/to/config.yaml
```

Older git versions use the equivalent `git checkout <sha>^ -- path/to/file`.

To read the old contents without touching the working tree:

```bash
git show <sha>^:path/to/config.yaml
```

If you cannot remember the path at all, search every version of every file for a
string you remember instead:

```bash
git log -S'DATABASE_URL' --oneline --all
```
