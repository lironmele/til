"""Turning loaded snippets into the static site, feed and README index."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .content import Snippet, group_by_topic, topic_label
from .markdown_lite import escape_attr, escape_text

INDEX_START = "<!-- index starts -->"
INDEX_END = "<!-- index ends -->"


class Templates:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._cache: dict[str, str] = {}

    def get(self, name: str) -> str:
        if name not in self._cache:
            self._cache[name] = (self.directory / name).read_text(encoding="utf-8")
        return self._cache[name]

    def render(self, name: str, **values: str) -> str:
        template = self.get(name)
        return re.sub(
            r"\{\{\s*(\w+)\s*\}\}",
            lambda m: str(values.get(m.group(1), "")),
            template,
        )


def format_date(value: datetime) -> str:
    # Built by hand because "%-d" is not portable across platforms.
    return "%d %s %d" % (value.day, value.strftime("%B"), value.year)


def escape(text: str) -> str:
    return escape_attr(text).replace(">", "&gt;")


def plural(count: int, noun: str) -> str:
    return "%d %s%s" % (count, noun, "" if count == 1 else "s")


class SiteBuilder:
    def __init__(self, root: Path, config: dict, snippets: list[Snippet]) -> None:
        self.root = root
        self.config = config
        self.snippets = snippets
        self.topics = group_by_topic(snippets)
        self.output = root / config["output_dir"]
        self.templates = Templates(root / "templates")

    # -- helpers ---------------------------------------------------------

    def label(self, topic: str) -> str:
        return topic_label(topic, self.config)

    def base_url(self) -> str:
        base = self.config.get("base_url", "").strip()
        return base if not base or base.endswith("/") else base + "/"

    def page(self, content: str, *, title: str, description: str, prefix: str, og_type: str = "website") -> str:
        site_title = self.config["title"]
        author = self.config.get("author", "")
        footer = "Built with a small Python script. %s" % (
            "Snippets by %s." % escape(author) if author else ""
        )
        return self.templates.render(
            "base.html",
            page_title=escape(title),
            site_title=escape(site_title),
            description=escape(description),
            og_type=og_type,
            root=prefix,
            repo_url=escape_attr(self.config.get("repo_url", "")) or (prefix + "index.html"),
            footer=footer,
            head_extra="",
            content=content,
        )

    def write(self, relative: str, text: str) -> None:
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def list_item(self, snippet: Snippet, prefix: str, show_topic: bool = True) -> str:
        topic_link = ""
        if show_topic:
            topic_link = '<a class="topic-tag" href="%s%s/index.html">%s</a>' % (
                prefix,
                snippet.topic,
                escape(self.label(snippet.topic)),
            )
        summary = escape_text(snippet.summary)
        return (
            '<li data-url="{url}" data-title="{title_attr}" data-topic="{topic_attr}" data-tags="{tags}">'
            '<div class="row">{topic_link}<time datetime="{iso}">{date}</time></div>'
            '<h2><a href="{prefix}{url}">{title}</a></h2>'
            "<p>{summary}</p></li>"
        ).format(
            url=snippet.url,
            title_attr=escape_attr(snippet.title),
            topic_attr=escape_attr(self.label(snippet.topic)),
            tags=escape_attr(" ".join(snippet.tags)),
            topic_link=topic_link,
            iso=snippet.date.date().isoformat(),
            date=format_date(snippet.date),
            prefix=prefix,
            title=escape(snippet.title),
            summary=summary,
        )

    # -- pages -----------------------------------------------------------

    def build(self) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        self.copy_static()
        self.build_index()
        self.build_topics()
        self.build_snippets()
        self.build_search_index()
        self.build_feed()
        self.build_sitemap()
        self.build_404()
        self.write_readme()

    def copy_static(self) -> None:
        static = self.root / "static"
        if not static.is_dir():
            return
        for item in static.iterdir():
            if item.is_file():
                shutil.copy2(item, self.output / item.name)
            else:
                shutil.copytree(item, self.output / item.name, dirs_exist_ok=True)

    EMPTY_STATE = (
        '<div class="empty-state">'
        "<p>No snippets yet. Add the first one with:</p>"
        '<div class="code-block"><pre><code>'
        "python3 build.py new python &quot;Something I learned&quot;\n"
        "python3 build.py --serve"
        "</code></pre></div>"
        "<p>Every snippet is a Markdown file under <code>til/&lt;topic&gt;/</code>. "
        "The first heading becomes the title and the folder name becomes the topic.</p>"
        "</div>"
    )

    def counts_line(self) -> str:
        if not self.snippets:
            return "Nothing here yet."
        return "%s across %s &middot; newest first" % (
            plural(len(self.snippets), "snippet"),
            plural(len(self.topics), "topic"),
        )

    def build_index(self) -> None:
        chips = "\n".join(
            '<a class="chip" href="%s/index.html">%s <span class="n">%d</span></a>'
            % (topic, escape(self.label(topic)), len(items))
            for topic, items in sorted(self.topics.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        )
        content = self.templates.render(
            "index.html",
            site_title=escape(self.config["title"]),
            description=escape(self.config["description"]),
            counts=self.counts_line(),
            topic_chips=chips,
            items="\n".join(self.list_item(snippet, "") for snippet in self.snippets),
            empty_state="" if self.snippets else self.EMPTY_STATE,
            hide_when_empty="" if self.snippets else " hidden",
        )
        self.write(
            "index.html",
            self.page(
                content,
                title=self.config["title"],
                description=self.config["description"],
                prefix="",
            ),
        )

    def build_topics(self) -> None:
        for topic, items in self.topics.items():
            label = self.label(topic)
            content = self.templates.render(
                "topic.html",
                root="../",
                topic=escape(label),
                counts=plural(len(items), "snippet"),
                items="\n".join(self.list_item(item, "../", show_topic=False) for item in items),
            )
            self.write(
                "%s/index.html" % topic,
                self.page(
                    content,
                    title="%s - %s" % (label, self.config["title"]),
                    description="%s about %s." % (plural(len(items), "snippet"), label),
                    prefix="../",
                ),
            )

    def build_snippets(self) -> None:
        for topic, items in self.topics.items():
            for index, snippet in enumerate(items):
                newer = items[index - 1] if index else None
                older = items[index + 1] if index + 1 < len(items) else None
                self.write(snippet.url, self.snippet_page(snippet, newer, older))

    def snippet_page(self, snippet: Snippet, newer: Snippet | None, older: Snippet | None) -> str:
        meta = ['<time datetime="%s">%s</time>' % (snippet.date.date().isoformat(), format_date(snippet.date))]
        if snippet.updated and snippet.updated.date() > snippet.date.date():
            meta.append("updated %s" % format_date(snippet.updated))
        meta.append(escape(self.label(snippet.topic)))
        tags = ""
        if snippet.tags:
            tags = '<ul class="tag-list">%s</ul>' % "".join(
                "<li>%s</li>" % escape(tag) for tag in snippet.tags
            )
        pager = []
        if older:
            pager.append('<a class="prev" href="%s.html">&larr; %s</a>' % (older.slug, escape(older.title)))
        if newer:
            pager.append('<a class="next" href="%s.html">%s &rarr;</a>' % (newer.slug, escape(newer.title)))
        content = self.templates.render(
            "til.html",
            root="../",
            topic=escape(self.label(snippet.topic)),
            topic_url="index.html",
            title=escape(snippet.title),
            meta=" &middot; ".join(meta),
            tags=tags,
            toc=self.toc(snippet),
            body=snippet.html,
            edit_url=self.edit_url(snippet),
            pager="\n".join(pager),
        )
        return self.page(
            content,
            title="%s - %s" % (snippet.title, self.config["title"]),
            description=snippet.summary or snippet.title,
            prefix="../",
            og_type="article",
        )

    def toc(self, snippet: Snippet) -> str:
        entries = [item for item in snippet.headings if item[0] in (2, 3)]
        if len(entries) < 3:
            return ""
        links = "\n".join(
            '<li class="level-%d"><a href="#%s">%s</a></li>' % (level, anchor, escape(text))
            for level, anchor, text in entries
        )
        return '<details class="toc"><summary>On this page</summary><ul>\n%s\n</ul></details>' % links

    def edit_url(self, snippet: Snippet) -> str:
        repo = self.config.get("repo_url", "").rstrip("/")
        if not repo:
            return "#"
        return "%s/blob/main/%s" % (repo, snippet.source_path)

    def build_search_index(self) -> None:
        payload = {
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "items": [
                {
                    "title": snippet.title,
                    "topic": self.label(snippet.topic),
                    "url": snippet.url,
                    "date": snippet.date.date().isoformat(),
                    "tags": snippet.tags,
                    "text": snippet.search_text,
                }
                for snippet in self.snippets
            ],
        }
        self.write("search.json", json.dumps(payload, ensure_ascii=False, indent=1))

    def build_feed(self) -> None:
        base = self.base_url()
        updated = max((s.updated or s.date for s in self.snippets), default=datetime.now(timezone.utc))
        entries = []
        for snippet in self.snippets[:30]:
            link = base + snippet.url
            entries.append(
                "\n".join(
                    [
                        "  <entry>",
                        "    <title>%s</title>" % xml_escape(snippet.title),
                        '    <link href="%s"/>' % xml_escape(link),
                        "    <id>%s</id>" % xml_escape(link or snippet.url),
                        "    <updated>%s</updated>" % (snippet.updated or snippet.date).isoformat(),
                        "    <published>%s</published>" % snippet.date.isoformat(),
                        '    <category term="%s"/>' % xml_escape(snippet.topic),
                        "    <summary>%s</summary>" % xml_escape(snippet.summary or snippet.title),
                        "  </entry>",
                    ]
                )
            )
        author = self.config.get("author") or self.config["title"]
        feed = "\n".join(
            [
                '<?xml version="1.0" encoding="utf-8"?>',
                '<feed xmlns="http://www.w3.org/2005/Atom">',
                "  <title>%s</title>" % xml_escape(self.config["title"]),
                "  <subtitle>%s</subtitle>" % xml_escape(self.config["description"]),
                '  <link href="%s" rel="alternate"/>' % xml_escape(base or "./"),
                '  <link href="%sfeed.xml" rel="self"/>' % xml_escape(base),
                "  <id>%s</id>" % xml_escape(base or self.config["title"]),
                "  <updated>%s</updated>" % updated.isoformat(),
                "  <author><name>%s</name></author>" % xml_escape(author),
                "\n".join(entries),
                "</feed>",
                "",
            ]
        )
        self.write("feed.xml", feed)

    def build_sitemap(self) -> None:
        base = self.base_url()
        urls = ["index.html"]
        urls += ["%s/index.html" % topic for topic in self.topics]
        urls += [snippet.url for snippet in self.snippets]
        body = "\n".join(
            "  <url><loc>%s%s</loc></url>" % (xml_escape(base), xml_escape(url)) for url in urls
        )
        self.write(
            "sitemap.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % body,
        )

    def build_404(self) -> None:
        content = self.templates.render("404.html", root="")
        self.write(
            "404.html",
            self.page(content, title="Not found", description="Page not found", prefix=""),
        )

    # -- repository README ----------------------------------------------

    def readme_index(self) -> str:
        if not self.snippets:
            return "## Index\n\n_No snippets yet._"
        lines = ["## Index", ""]
        for topic, items in self.topics.items():
            lines.append("### %s" % self.label(topic))
            lines.append("")
            for snippet in items:  # already newest first from collect()
                # Escape emphasis characters so titles like __slots__ survive
                # GitHub's own Markdown rendering of this file.
                title = re.sub(r"([_*])", r"\\\1", snippet.title)
                lines.append(
                    "* [%s](%s) - %s" % (title, snippet.source_path, snippet.date.date().isoformat())
                )
            lines.append("")
        lines.append(
            "_%s across %s._" % (plural(len(self.snippets), "snippet"), plural(len(self.topics), "topic"))
        )
        return "\n".join(lines)

    def write_readme(self) -> None:
        path = self.root / "README.md"
        index = "%s\n\n%s\n\n%s" % (INDEX_START, self.readme_index(), INDEX_END)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if INDEX_START in existing and INDEX_END in existing:
                head, _, rest = existing.partition(INDEX_START)
                _, _, tail = rest.partition(INDEX_END)
                path.write_text(head + index + tail, encoding="utf-8")
                return
            path.write_text(existing.rstrip() + "\n\n" + index + "\n", encoding="utf-8")
            return
        path.write_text(
            "# %s\n\n%s\n\n%s\n" % (self.config["title"], self.config["description"], index),
            encoding="utf-8",
        )
