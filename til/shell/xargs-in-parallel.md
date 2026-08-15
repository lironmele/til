---
tags: xargs, find, parallel
---

# Run a command in parallel with xargs -P

`xargs -P N` runs up to N processes at once — no need for GNU parallel:

```bash
find . -name '*.png' -print0 | xargs -0 -P 8 -I{} optipng -quiet {}
```

The pieces that matter:

* `-print0` / `-0` pair up so paths with spaces or newlines survive.
* `-P 8` sets the concurrency. `-P 0` means "as many as possible", which is
  usually not what you want on a laptop.
* `-I{}` substitutes each argument, and implies one argument per command, so
  each file becomes its own process.

Without `-I`, xargs packs as many arguments as fit into each command, which is
much faster when the command accepts many inputs:

```bash
find . -name '*.py' -print0 | xargs -0 -P 4 -n 20 ruff check
```

Output from parallel jobs interleaves line by line, so pipe through
`xargs -P 4 -I{} sh -c 'echo "== {}"; some-command {}'` when you need to tell
which output came from which input. GNU xargs also has `-a FILE` to read
arguments from a file instead of stdin.
