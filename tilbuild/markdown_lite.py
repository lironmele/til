"""A small dependency-free Markdown renderer.

It covers the subset of Markdown that TIL notes actually use: headings, fenced
and indented code, lists, blockquotes, tables, horizontal rules, inline
formatting, links, images and raw HTML passthrough.

Deliberately unsupported: reference-style links, footnotes, setext headings and
nested block quoting inside lists beyond one level. Anything not understood is
emitted as a plain paragraph rather than dropped.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["render", "slugify", "strip_markdown", "first_heading"]

PLACEHOLDER = "\x00{}\x00"
PLACEHOLDER_RE = re.compile("\x00(\\d+)\x00")

FENCE_RE = re.compile(r"^(\s{0,3})(`{3,}|~{3,})\s*([^`\s]*)\s*$")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HR_RE = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
BULLET_RE = re.compile(r"^(\s*)([-*+])\s+(.*)$")
ORDERED_RE = re.compile(r"^(\s*)(\d{1,9})[.)]\s+(.*)$")
QUOTE_RE = re.compile(r"^ {0,3}>\s?(.*)$")
TABLE_DIVIDER_RE = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")
HTML_BLOCK_RE = re.compile(
    r"^\s*</?(?:div|details|summary|table|thead|tbody|tr|td|th|p|ul|ol|li|pre|"
    r"blockquote|figure|figcaption|section|article|aside|hr|img|iframe|video|"
    r"audio|svg|h[1-6])\b",
    re.IGNORECASE,
)
RAW_TAG_RE = re.compile(r"</?[a-zA-Z][^<>]*>|<!--.*?-->", re.DOTALL)
ENTITY_RE = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]{1,31});")
CODE_SPAN_RE = re.compile(r"(?<!\\)(`+)(.+?)\1", re.DOTALL)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(\s*(<[^>]*>|[^\s)]*)(?:\s+[\"']([^\"']*)[\"'])?\s*\)")
LINK_RE = re.compile(r"\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*(<[^>]*>|[^\s)]*)(?:\s+[\"']([^\"']*)[\"'])?\s*\)")
AUTOLINK_RE = re.compile(r"<((?:https?|mailto):[^>\s]+)>")
BARE_URL_RE = re.compile(r"(?<![\"'=(>\w])(https?://[^\s<>\"')]+[^\s<>\"').,;:!?])")
STRONG_RE = re.compile(r"(?<!\w)\*\*(?=\S)(.+?)(?<=\S)\*\*|(?<!\w)__(?=\S)(.+?)(?<=\S)__", re.DOTALL)
EM_RE = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])|(?<![\w_])_(?=\S)([^_]+?)(?<=\S)_(?![\w_])")
DEL_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.DOTALL)
ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!~|>])")
MD_STRIP_RE = re.compile(r"[*_`~#>]|!?\[|\]\([^)]*\)|^\s*[-*+]\s+", re.MULTILINE)


def slugify(text: str) -> str:
    """Turn a heading or filename into a URL-safe slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def escape_attr(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def escape_code(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_text(text: str) -> str:
    """Escape HTML special characters, but let deliberate raw HTML through."""
    out = []
    pos = 0
    for match in RAW_TAG_RE.finditer(text):
        out.append(_escape_plain(text[pos : match.start()]))
        out.append(match.group(0))
        pos = match.end()
    out.append(_escape_plain(text[pos:]))
    return "".join(out)


def _escape_plain(text: str) -> str:
    parts = []
    pos = 0
    for match in ENTITY_RE.finditer(text):
        parts.append(text[pos : match.start()].replace("&", "&amp;"))
        parts.append(match.group(0))
        pos = match.end()
    parts.append(text[pos:].replace("&", "&amp;"))
    return "".join(parts).replace("<", "&lt;").replace(">", "&gt;")


class Inline:
    """Inline renderer. Fragments that must survive later passes are parked in
    placeholder slots and spliced back in at the end."""

    def __init__(self) -> None:
        self.slots: list[str] = []

    def park(self, html: str) -> str:
        self.slots.append(html)
        return PLACEHOLDER.format(len(self.slots) - 1)

    def unpark(self, text: str) -> str:
        # Slots can contain other placeholders, so keep expanding until stable.
        for _ in range(10):
            new = PLACEHOLDER_RE.sub(lambda m: self.slots[int(m.group(1))], text)
            if new == text:
                break
            text = new
        return text

    def render(self, text: str) -> str:
        text = CODE_SPAN_RE.sub(
            lambda m: self.park("<code>" + escape_code(m.group(2).strip()) + "</code>"), text
        )
        # Park backslash escapes before any other rule can see the character.
        text = ESCAPE_RE.sub(lambda m: self.park(_escape_plain(m.group(1))), text)
        text = escape_text(text)
        text = AUTOLINK_RE.sub(lambda m: self.park(self._anchor(m.group(1), m.group(1))), text)
        text = IMAGE_RE.sub(self._image, text)
        text = LINK_RE.sub(self._link, text)
        text = BARE_URL_RE.sub(lambda m: self.park(self._anchor(m.group(1), m.group(1))), text)
        text = STRONG_RE.sub(lambda m: "<strong>%s</strong>" % (m.group(1) or m.group(2)), text)
        text = EM_RE.sub(lambda m: "<em>%s</em>" % (m.group(1) or m.group(2)), text)
        text = DEL_RE.sub(lambda m: "<del>%s</del>" % m.group(1), text)
        text = re.sub(r"(  +|\\)\n", "<br>\n", text)
        return self.unpark(text)

    def _anchor(self, href: str, label: str, title: str | None = None) -> str:
        attrs = ' title="%s"' % escape_attr(title) if title else ""
        if href.startswith(("http://", "https://")):
            attrs += ' rel="noopener"'
        return '<a href="%s"%s>%s</a>' % (escape_attr(href), attrs, label)

    def _clean_url(self, url: str) -> str:
        url = url.strip()
        if url.startswith("<") and url.endswith(">"):
            url = url[1:-1]
        return url

    def _image(self, match: re.Match[str]) -> str:
        alt, url, title = match.group(1), self._clean_url(match.group(2)), match.group(3)
        attrs = ' title="%s"' % escape_attr(title) if title else ""
        return self.park(
            '<img src="%s" alt="%s"%s loading="lazy">' % (escape_attr(url), escape_attr(alt), attrs)
        )

    def _link(self, match: re.Match[str]) -> str:
        label, url, title = match.group(1), self._clean_url(match.group(2)), match.group(3)
        return self.park(self._anchor(url, self.render(label), title))


def render_inline(text: str) -> str:
    return Inline().render(text)


class Blocks:
    def __init__(self, lines: list[str], heading_ids: bool = True) -> None:
        self.lines = lines
        self.pos = 0
        self.heading_ids = heading_ids
        self.headings: list[tuple[int, str, str]] = []
        self._seen_ids: dict[str, int] = {}

    def peek(self) -> str | None:
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def run(self) -> str:
        out: list[str] = []
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            if not line.strip():
                self.pos += 1
                continue
            for handler in (
                self.fence,
                self.heading,
                self.rule,
                self.quote,
                self.listing,
                self.table,
                self.indented_code,
                self.raw_html,
            ):
                html = handler(line)
                if html is not None:
                    out.append(html)
                    break
            else:
                out.append(self.paragraph())
        return "\n".join(out)

    def fence(self, line: str) -> str | None:
        match = FENCE_RE.match(line)
        if not match:
            return None
        indent, marker, lang = match.group(1), match.group(2), match.group(3)
        self.pos += 1
        body: list[str] = []
        while self.pos < len(self.lines):
            current = self.lines[self.pos]
            closing = FENCE_RE.match(current)
            if closing and closing.group(2)[0] == marker[0] and len(closing.group(2)) >= len(marker):
                self.pos += 1
                break
            body.append(current[len(indent) :] if current.startswith(indent) else current)
            self.pos += 1
        attr = ' class="language-%s"' % escape_attr(lang) if lang else ""
        label = '<span class="code-lang">%s</span>' % escape_attr(lang) if lang else ""
        return '<div class="code-block">%s<pre><code%s>%s</code></pre></div>' % (
            label,
            attr,
            escape_code("\n".join(body)),
        )

    def heading(self, line: str) -> str | None:
        match = HEADING_RE.match(line)
        if not match:
            return None
        self.pos += 1
        level = len(match.group(1))
        text = render_inline(match.group(2))
        if not self.heading_ids:
            return "<h%d>%s</h%d>" % (level, text, level)
        anchor = self._unique_id(slugify(strip_markdown(match.group(2))))
        self.headings.append((level, anchor, strip_markdown(match.group(2))))
        return '<h%d id="%s">%s<a class="anchor" href="#%s" aria-label="Link to this section">#</a></h%d>' % (
            level,
            anchor,
            text,
            anchor,
            level,
        )

    def _unique_id(self, anchor: str) -> str:
        count = self._seen_ids.get(anchor, 0)
        self._seen_ids[anchor] = count + 1
        return anchor if not count else "%s-%d" % (anchor, count)

    def rule(self, line: str) -> str | None:
        if not HR_RE.match(line):
            return None
        self.pos += 1
        return "<hr>"

    def quote(self, line: str) -> str | None:
        if not QUOTE_RE.match(line):
            return None
        body: list[str] = []
        while self.pos < len(self.lines):
            match = QUOTE_RE.match(self.lines[self.pos])
            if match:
                body.append(match.group(1))
            elif self.lines[self.pos].strip() and body:
                body.append(self.lines[self.pos])  # lazy continuation
            else:
                break
            self.pos += 1
        return "<blockquote>\n%s\n</blockquote>" % render_blocks(body)

    def listing(self, line: str) -> str | None:
        bullet, ordered = BULLET_RE.match(line), ORDERED_RE.match(line)
        if not bullet and not ordered:
            return None
        base_indent = len((bullet or ordered).group(1))
        tag = "ul" if bullet else "ol"
        start = ""
        if ordered and ordered.group(2) != "1":
            start = ' start="%s"' % ordered.group(2)
        items: list[list[str]] = []
        loose = False
        pending_blank = False
        while self.pos < len(self.lines):
            current = self.lines[self.pos]
            if not current.strip():
                if not items:
                    break
                pending_blank = True
                self.pos += 1
                continue
            item = BULLET_RE.match(current) if tag == "ul" else ORDERED_RE.match(current)
            indent = len(current) - len(current.lstrip())
            if item and len(item.group(1)) == base_indent:
                if pending_blank and items:
                    loose = True
                items.append([item.group(3)])
            elif items and indent > base_indent:
                if pending_blank:
                    loose = True
                    items[-1].append("")
                items[-1].append(current[base_indent + 2 :] if len(current) > base_indent + 2 else current.strip())
            elif items and not pending_blank and not item and indent >= base_indent:
                items[-1].append(current.strip())  # lazy continuation
            else:
                break
            pending_blank = False
            self.pos += 1
        rendered = []
        for item_lines in items:
            html = render_blocks(item_lines)
            if not loose and html.startswith("<p>") and html.endswith("</p>") and "<p>" not in html[3:]:
                html = html[3:-4]
            rendered.append("<li>%s</li>" % html)
        return "<%s%s>\n%s\n</%s>" % (tag, start, "\n".join(rendered), tag)

    def table(self, line: str) -> str | None:
        if "|" not in line or self.pos + 1 >= len(self.lines):
            return None
        if not TABLE_DIVIDER_RE.match(self.lines[self.pos + 1]):
            return None
        divider = self._split_row(self.lines[self.pos + 1])
        aligns = []
        for cell in divider:
            left, right = cell.startswith(":"), cell.endswith(":")
            aligns.append("center" if left and right else "right" if right else "left" if left else "")
        header = self._split_row(line)
        self.pos += 2
        body_rows = []
        while self.pos < len(self.lines) and "|" in self.lines[self.pos] and self.lines[self.pos].strip():
            body_rows.append(self._split_row(self.lines[self.pos]))
            self.pos += 1
        out = ["<table>", "<thead>", "<tr>"]
        out += [self._cell("th", value, aligns, i) for i, value in enumerate(header)]
        out += ["</tr>", "</thead>", "<tbody>"]
        for row in body_rows:
            out.append("<tr>")
            out += [self._cell("td", value, aligns, i) for i, value in enumerate(row)]
            out.append("</tr>")
        out += ["</tbody>", "</table>"]
        return "\n".join(out)

    @staticmethod
    def _split_row(line: str) -> list[str]:
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|") and not line.endswith("\\|"):
            line = line[:-1]
        return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)]

    @staticmethod
    def _cell(tag: str, value: str, aligns: list[str], index: int) -> str:
        align = aligns[index] if index < len(aligns) else ""
        attr = ' style="text-align:%s"' % align if align else ""
        return "<%s%s>%s</%s>" % (tag, attr, render_inline(value), tag)

    def indented_code(self, line: str) -> str | None:
        if not line.startswith("    "):
            return None
        body = []
        while self.pos < len(self.lines):
            current = self.lines[self.pos]
            if current.startswith("    "):
                body.append(current[4:])
            elif not current.strip():
                body.append("")
            else:
                break
            self.pos += 1
        while body and not body[-1].strip():
            body.pop()
        return '<div class="code-block"><pre><code>%s</code></pre></div>' % escape_code("\n".join(body))

    def raw_html(self, line: str) -> str | None:
        if not HTML_BLOCK_RE.match(line):
            return None
        body = []
        while self.pos < len(self.lines) and self.lines[self.pos].strip():
            body.append(self.lines[self.pos])
            self.pos += 1
        return "\n".join(body)

    def paragraph(self) -> str:
        body = []
        while self.pos < len(self.lines):
            current = self.lines[self.pos]
            if not current.strip():
                break
            if body and (
                HEADING_RE.match(current)
                or FENCE_RE.match(current)
                or HR_RE.match(current)
                or QUOTE_RE.match(current)
                or BULLET_RE.match(current)
                or ORDERED_RE.match(current)
            ):
                break
            body.append(current.strip())
            self.pos += 1
        return "<p>%s</p>" % render_inline("\n".join(body))


def render_blocks(lines: list[str]) -> str:
    return Blocks(lines, heading_ids=False).run()


def render(text: str, with_headings: bool = False):
    """Render Markdown to HTML. With ``with_headings`` also return the heading
    outline as ``(level, anchor, text)`` tuples."""
    parser = Blocks(text.replace("\r\n", "\n").replace("\t", "    ").split("\n"))
    html = parser.run()
    return (html, parser.headings) if with_headings else html


def strip_markdown(text: str) -> str:
    """Best-effort plain text, for titles, search text and feed summaries."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    # Code spans keep their contents verbatim: `__slots__` must not lose its
    # underscores to the emphasis stripping below, so park it first.
    parked: list[str] = []

    def park(match: re.Match[str]) -> str:
        parked.append(match.group(2))
        return PLACEHOLDER.format(len(parked) - 1)

    text = CODE_SPAN_RE.sub(park, text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = MD_STRIP_RE.sub("", text)
    text = PLACEHOLDER_RE.sub(lambda m: parked[int(m.group(1))], text)
    return re.sub(r"\s+", " ", text).strip()


def first_heading(text: str) -> str | None:
    for line in text.split("\n"):
        match = HEADING_RE.match(line)
        if match:
            return strip_markdown(match.group(2))
    return None
