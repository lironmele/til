import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tilbuild import markdown_lite as md


class TestInline(unittest.TestCase):
    def test_emphasis(self):
        self.assertEqual(md.render("*a* **b** ~~c~~"), "<p><em>a</em> <strong>b</strong> <del>c</del></p>")

    def test_snake_case_is_not_emphasis(self):
        self.assertIn("some_var_name", md.render("some_var_name here"))

    def test_code_span_wins_over_emphasis(self):
        self.assertEqual(md.render("`*not em*`"), "<p><code>*not em*</code></p>")

    def test_link(self):
        html = md.render("[docs](https://example.com/a_b)")
        self.assertIn('href="https://example.com/a_b"', html)
        self.assertIn(">docs</a>", html)

    def test_link_title_and_nested_formatting(self):
        html = md.render('[**bold** link](/x "Title")')
        self.assertIn('title="Title"', html)
        self.assertIn("<strong>bold</strong>", html)

    def test_image(self):
        html = md.render("![alt text](cat.png)")
        self.assertIn('<img src="cat.png" alt="alt text"', html)

    def test_autolink_and_bare_url(self):
        self.assertIn('href="https://a.example"', md.render("<https://a.example>"))
        self.assertIn('href="https://b.example/x"', md.render("see https://b.example/x now"))

    def test_html_is_escaped_but_tags_pass_through(self):
        self.assertIn("a &lt;= b", md.render("a <= b"))
        self.assertIn("<kbd>x</kbd>", md.render("<kbd>x</kbd>"))

    def test_backslash_escape(self):
        self.assertEqual(md.render(r"\*literal\*"), "<p>*literal*</p>")


class TestBlocks(unittest.TestCase):
    def test_heading_gets_anchor_id(self):
        html = md.render("## The Catch")
        self.assertIn('<h2 id="the-catch">', html)

    def test_duplicate_headings_get_unique_ids(self):
        html = md.render("## Notes\n\n## Notes")
        self.assertIn('id="notes"', html)
        self.assertIn('id="notes-1"', html)

    def test_fenced_code_keeps_markdown_literal(self):
        html = md.render("```python\nx = **1**\n```")
        self.assertIn('class="language-python"', html)
        self.assertIn("x = **1**", html)

    def test_fenced_code_escapes_html(self):
        self.assertIn("&lt;div&gt;", md.render("```\n<div>\n```"))

    def test_indented_code(self):
        self.assertIn("<pre><code>x = 1", md.render("    x = 1\n    y = 2"))

    def test_unordered_list(self):
        html = md.render("* one\n* two")
        self.assertEqual(html, "<ul>\n<li>one</li>\n<li>two</li>\n</ul>")

    def test_ordered_list_start(self):
        self.assertIn('<ol start="3">', md.render("3. three\n4. four"))

    def test_nested_list(self):
        html = md.render("* one\n  * inner\n* two")
        self.assertIn("<ul>\n<li>inner</li>\n</ul>", html)

    def test_blockquote(self):
        self.assertIn("<blockquote>", md.render("> quoted\n> lines"))

    def test_table_alignment(self):
        html = md.render("| a | b |\n| --- | ---: |\n| 1 | 2 |")
        self.assertIn("<th>a</th>", html)
        self.assertIn('<td style="text-align:right">2</td>', html)

    def test_horizontal_rule(self):
        self.assertIn("<hr>", md.render("---"))

    def test_headings_are_reported(self):
        _, headings = md.render("# Title\n\n## Two\n\n### Three", with_headings=True)
        self.assertEqual([(1, "title", "Title"), (2, "two", "Two"), (3, "three", "Three")], headings)

    def test_paragraph_stops_at_block(self):
        html = md.render("text\n* item")
        self.assertIn("<p>text</p>", html)
        self.assertIn("<li>item</li>", html)


class TestHelpers(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(md.slugify("Hello, World! -- 2"), "hello-world-2")
        self.assertEqual(md.slugify("café crème"), "cafe-creme")

    def test_first_heading(self):
        self.assertEqual(md.first_heading("intro\n\n# The Title\n"), "The Title")
        self.assertIsNone(md.first_heading("no headings here"))

    def test_strip_markdown(self):
        self.assertEqual(md.strip_markdown("**bold** and [a link](http://x)"), "bold and a link")

    def test_strip_markdown_keeps_code_span_contents(self):
        self.assertEqual(
            md.strip_markdown("Dataclasses can generate `__slots__` for you"),
            "Dataclasses can generate __slots__ for you",
        )

    def test_strip_markdown_drops_fenced_code(self):
        self.assertEqual(md.strip_markdown("text\n\n```\nx = 1\n```\n\nmore"), "text more")


if __name__ == "__main__":
    unittest.main()
