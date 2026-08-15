---
tags: stdlib, cli
---

# Serve any directory with http.server --directory

`python -m http.server` serves the current working directory, but since Python
3.7 it takes `--directory`, so there is no need to `cd` first:

```bash
python3 -m http.server 8000 --directory ./site
```

Useful flags:

| Flag | What it does |
| --- | --- |
| `--directory DIR` | Serve `DIR` instead of the working directory |
| `--bind 127.0.0.1` | Only listen on localhost instead of every interface |
| `--protocol HTTP/1.1` | Keep-alive connections (Python 3.11+) |

The default binds to `0.0.0.0`, which means everyone on the same network can
read the directory. On shared wifi, always pass `--bind 127.0.0.1`.

It is single-threaded per request and has no cache headers to speak of — fine
for previewing a static build, not for anything else.
