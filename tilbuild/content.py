"""Discovering snippets on disk and working out when they were written."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import markdown_lite as md

DEFAULT_CONFIG = {
    "title": "TIL",
    "description": "Today I Learned - short notes on things I picked up along the way.",
    "author": "",
    "base_url": "",
    "repo_url": "",
    "source_dir": "til",
    "output_dir": "site",
    "topic_names": {},
}

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class Snippet:
    topic: str
    slug: str
    path: Path
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    rel_path: str = ""
    created: datetime | None = None
    updated: datetime | None = None
    html: str = ""
    headings: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def url(self) -> str:
        """Site-root-relative URL, e.g. ``python/enum-str.html``."""
        return "%s/%s.html" % (self.topic, self.slug)

    @property
    def source_path(self) -> str:
        """Path to the Markdown file, relative to the repository root."""
        return self.rel_path or self.path.as_posix()

    @property
    def date(self) -> datetime:
        return self.created or self.updated or datetime.now(timezone.utc)

    @property
    def summary(self) -> str:
        """First paragraph of prose, used for listings and the feed."""
        for block in re.split(r"\n\s*\n", self.body.strip()):
            block = block.strip()
            if not block or block.startswith(("#", "```", ">", "|", "    ")):
                continue
            text = md.strip_markdown(block)
            if text:
                return text if len(text) <= 220 else text[:217].rsplit(" ", 1)[0] + "…"
        return ""

    @property
    def search_text(self) -> str:
        return md.strip_markdown(self.body)[:4000]


def load_config(root: Path) -> dict:
    config = dict(DEFAULT_CONFIG)
    config_path = root / "site.json"
    if config_path.exists():
        config.update(json.loads(config_path.read_text(encoding="utf-8")))
    return config


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Parse an optional ``---`` delimited block of ``key: value`` pairs."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip().lower()] = value.strip().strip("\"'")
    return meta, text[match.end() :]


def parse_date(value: str) -> datetime | None:
    value = value.strip().replace("Z", "+00:00")
    for parse in (
        datetime.fromisoformat,
        lambda v: datetime.strptime(v, "%Y-%m-%d"),
        lambda v: datetime.strptime(v, "%Y/%m/%d"),
    ):
        try:
            parsed = parse(value)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def load_snippet(path: Path, source_dir: Path) -> Snippet:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    title = meta.get("title") or md.first_heading(body) or path.stem.replace("-", " ").capitalize()
    if not meta.get("title"):
        # Drop the leading H1 from the body; the template renders the title.
        body = re.sub(r"\A\s*#\s+.*\n", "", body, count=1)
    tags = [tag.strip() for tag in re.split(r"[,\s]+", meta.get("tags", "")) if tag.strip()]
    relative = path.relative_to(source_dir)
    snippet = Snippet(
        topic=relative.parts[0] if len(relative.parts) > 1 else "misc",
        slug=md.slugify(path.stem),
        path=path,
        title=title,
        body=body.strip(),
        tags=tags,
    )
    for key, attr in (("date", "created"), ("created", "created"), ("updated", "updated")):
        if meta.get(key):
            setattr(snippet, attr, parse_date(meta[key]))
    snippet.html, snippet.headings = md.render(snippet.body, with_headings=True)
    return snippet


def git_dates(root: Path, source_dir: Path) -> dict[str, tuple[datetime, datetime]]:
    """Map ``path -> (first commit, last commit)`` in one ``git log`` pass."""
    try:
        output = subprocess.run(
            ["git", "log", "--format=%x1e%aI", "--name-only", "--", source_dir.as_posix()],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if output.returncode != 0:
        return {}
    dates: dict[str, list[datetime]] = {}
    stamp: datetime | None = None
    for chunk in output.stdout.split("\x1e"):
        lines = [line for line in chunk.split("\n") if line.strip()]
        if not lines:
            continue
        stamp = parse_date(lines[0])
        if stamp is None:
            continue
        for name in lines[1:]:
            dates.setdefault(name, []).append(stamp)
    return {name: (min(stamps), max(stamps)) for name, stamps in dates.items()}


def collect(root: Path, config: dict) -> list[Snippet]:
    """Load every snippet under the source directory, newest first."""
    source_dir = root / config["source_dir"]
    if not source_dir.is_dir():
        return []
    history = git_dates(root, Path(config["source_dir"]))
    snippets = []
    for path in sorted(source_dir.rglob("*.md")):
        if path.name.startswith("_") or path.name.lower() == "readme.md":
            continue
        snippet = load_snippet(path, source_dir)
        snippet.rel_path = path.relative_to(root).as_posix()
        tracked = history.get(snippet.rel_path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)
        # Front matter wins, then git history, then the file's mtime. An
        # untracked file dated by front matter is not reported as "updated".
        snippet.created = snippet.created or (tracked[0] if tracked else mtime)
        snippet.updated = snippet.updated or (tracked[1] if tracked else snippet.created)
        snippets.append(snippet)
    # Newest first, with same-day snippets in alphabetical order.
    snippets.sort(key=lambda item: item.title.lower())
    snippets.sort(key=lambda item: item.date, reverse=True)
    return snippets


def group_by_topic(snippets: list[Snippet]) -> dict[str, list[Snippet]]:
    topics: dict[str, list[Snippet]] = {}
    for snippet in snippets:
        topics.setdefault(snippet.topic, []).append(snippet)
    return dict(sorted(topics.items()))


def topic_label(topic: str, config: dict) -> str:
    return config.get("topic_names", {}).get(topic, topic)
