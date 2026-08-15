import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tilbuild import content
from tilbuild.render import SiteBuilder


class TestFrontMatter(unittest.TestCase):
    def test_parses_keys_and_strips_block(self):
        meta, body = content.parse_front_matter("---\ntags: a, b\ndate: 2024-05-01\n---\n\n# Hi\n")
        self.assertEqual({"tags": "a, b", "date": "2024-05-01"}, meta)
        self.assertEqual("# Hi\n", body)

    def test_no_front_matter_is_left_alone(self):
        meta, body = content.parse_front_matter("# Hi\n\n---\n")
        self.assertEqual({}, meta)
        self.assertEqual("# Hi\n\n---\n", body)

    def test_parse_date_formats(self):
        self.assertEqual(2024, content.parse_date("2024-05-01").year)
        self.assertEqual(2024, content.parse_date("2024-05-01T10:00:00Z").year)
        self.assertIsNone(content.parse_date("last tuesday"))


class TestBuild(unittest.TestCase):
    """Build a throwaway site from a temporary source tree."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        shutil.copytree(ROOT / "templates", self.tmp / "templates")
        shutil.copytree(ROOT / "static", self.tmp / "static")
        source = self.tmp / "til" / "python"
        source.mkdir(parents=True)
        (source / "first-note.md").write_text(
            "---\ntags: alpha, beta\ndate: 2024-01-02\n---\n\n"
            "# First note\n\nA paragraph about `code`.\n\n## Detail\n\n* one\n* two\n",
            encoding="utf-8",
        )
        (source / "second-note.md").write_text(
            "---\ndate: 2024-03-04\n---\n\n# Second note\n\nAnother paragraph.\n", encoding="utf-8"
        )
        (self.tmp / "site.json").write_text(
            json.dumps(
                {
                    "title": "Test TIL",
                    "description": "Testing",
                    "base_url": "https://example.com/til/",
                    "repo_url": "https://github.com/example/til",
                    "topic_names": {"python": "Python"},
                }
            ),
            encoding="utf-8",
        )
        self.config = content.load_config(self.tmp)
        self.snippets = content.collect(self.tmp, self.config)
        self.builder = SiteBuilder(self.tmp, self.config, self.snippets)
        self.builder.build()
        self.out = self.tmp / "site"

    def read(self, name):
        return (self.out / name).read_text(encoding="utf-8")

    def test_collects_snippets_newest_first(self):
        self.assertEqual(["Second note", "First note"], [s.title for s in self.snippets])
        self.assertEqual("python", self.snippets[0].topic)
        self.assertEqual(["alpha", "beta"], self.snippets[1].tags)

    def test_same_day_snippets_sort_alphabetically(self):
        same_day = self.tmp / "til" / "python"
        for title in ("Zebra note", "Alpha note"):
            (same_day / ("%s.md" % title.split()[0].lower())).write_text(
                "---\ndate: 2025-06-01\n---\n\n# %s\n\nBody.\n" % title, encoding="utf-8"
            )
        titles = [s.title for s in content.collect(self.tmp, self.config)]
        self.assertEqual(["Alpha note", "Zebra note"], titles[:2])

    def test_front_matter_date_wins(self):
        self.assertEqual("2024-01-02", self.snippets[1].date.date().isoformat())

    def test_expected_files_exist(self):
        for name in (
            "index.html",
            "python/index.html",
            "python/first-note.html",
            "python/second-note.html",
            "search.json",
            "feed.xml",
            "sitemap.xml",
            "404.html",
            "style.css",
            "til.js",
        ):
            self.assertTrue((self.out / name).exists(), name)

    def test_index_links_every_snippet(self):
        index = self.read("index.html")
        self.assertIn('href="python/first-note.html"', index)
        self.assertIn('href="python/second-note.html"', index)
        self.assertIn("2 snippets across 1 topics", index)

    def test_snippet_page_renders_body_and_meta(self):
        page = self.read("python/first-note.html")
        self.assertIn("<h1>First note</h1>", page)
        self.assertIn("<code>code</code>", page)
        self.assertIn('<h2 id="detail">', page)
        self.assertIn("2 January 2024", page)
        self.assertIn("<li>alpha</li>", page)
        self.assertIn("https://github.com/example/til/blob/main/til/python/first-note.md", page)
        # relative asset paths keep the site portable under any base path
        self.assertIn('href="../style.css"', page)

    def test_title_is_not_duplicated_in_body(self):
        self.assertEqual(1, self.read("python/first-note.html").count("First note</h1>"))

    def test_pager_links_neighbours(self):
        self.assertIn('href="first-note.html"', self.read("python/second-note.html"))

    def test_search_index_has_full_text(self):
        payload = json.loads(self.read("search.json"))
        self.assertEqual(2, len(payload["items"]))
        self.assertIn("A paragraph about code", payload["items"][1]["text"])

    def test_feed_uses_absolute_urls(self):
        feed = self.read("feed.xml")
        self.assertIn("https://example.com/til/python/second-note.html", feed)
        self.assertIn("<title>Test TIL</title>", feed)

    def test_readme_index_is_generated_and_idempotent(self):
        readme = (self.tmp / "README.md").read_text(encoding="utf-8")
        self.assertIn("* [First note](til/python/first-note.md) - 2024-01-02", readme)
        SiteBuilder(self.tmp, self.config, self.snippets).build()
        rebuilt = (self.tmp / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme, rebuilt)
        self.assertEqual(1, rebuilt.count("<!-- index starts -->"))

    def test_readme_preserves_hand_written_intro(self):
        (self.tmp / "README.md").write_text(
            "# My notes\n\nHand written intro.\n\n<!-- index starts -->\nstale\n<!-- index ends -->\n\nFooter.\n",
            encoding="utf-8",
        )
        SiteBuilder(self.tmp, self.config, self.snippets).build()
        readme = (self.tmp / "README.md").read_text(encoding="utf-8")
        self.assertIn("Hand written intro.", readme)
        self.assertIn("Footer.", readme)
        self.assertNotIn("stale", readme)

    def test_no_snippets_still_builds(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, empty)
        shutil.copytree(ROOT / "templates", empty / "templates")
        shutil.copytree(ROOT / "static", empty / "static")
        config = content.load_config(empty)
        SiteBuilder(empty, config, content.collect(empty, config)).build()
        self.assertTrue((empty / "site" / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
