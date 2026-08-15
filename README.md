# TIL

Small things I learned, written down before I forget them — inspired by
[simonw/til](https://github.com/simonw/til).

Every snippet is a Markdown file in `til/<topic>/<slug>.md`. A single Python
script turns them into a static site: no dependencies, no build toolchain, no
lock file. Published at <https://lironmele.github.io/til/>.

## Adding a snippet

```bash
python3 build.py new python "Serve any directory with http.server"
$EDITOR til/python/serve-any-directory-with-http-server.md
python3 build.py --serve          # preview at http://localhost:8000
git add . && git commit -m "TIL: serve any directory" && git push
```

Pushing to `main` rebuilds and deploys the site through GitHub Actions.

A snippet is just Markdown. The first `# heading` becomes the title, the first
paragraph becomes the summary used in listings and the feed, and the folder name
becomes the topic. Optional front matter adds tags or pins a date:

```markdown
---
tags: cli, stdlib
date: 2024-05-01
---

# Serve any directory with http.server
```

Dates come from git history when front matter does not set them: first commit is
the published date, most recent commit shows as "updated".

## Commands

| Command | What it does |
| --- | --- |
| `python3 build.py` | Build the site into `site/` and refresh the index below |
| `python3 build.py --serve` | Build, then serve `site/` on port 8000 |
| `python3 build.py --clean` | Delete `site/` before building |
| `python3 build.py new TOPIC TITLE` | Scaffold a new snippet file |
| `python3 -m unittest discover -s tests` | Run the tests |

## How it works

| Path | Purpose |
| --- | --- |
| `build.py` | Command line entry point |
| `tilbuild/markdown_lite.py` | Dependency-free Markdown renderer |
| `tilbuild/content.py` | Finds snippets, reads front matter, dates them from git |
| `tilbuild/render.py` | Writes pages, `search.json`, `feed.xml`, `sitemap.xml`, this index |
| `templates/`, `static/` | Page templates and the CSS/JS copied into the build |
| `site.json` | Site title, description, base URL, topic display names |

The generated `site/` directory is git-ignored; GitHub Actions builds it on
every push. Search is client-side: titles and summaries filter instantly, and
`search.json` is fetched on the first keystroke for full-text matches.

<!-- index starts -->

## Index

### Python

* [Send a traceback across the network with tblib](til/python/send-a-traceback-across-the-network-with-tblib.md) - 2026-08-15

_1 snippet across 1 topic._

<!-- index ends -->
