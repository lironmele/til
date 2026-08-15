#!/usr/bin/env python3
"""Build the TIL site.

    python3 build.py              # build into site/
    python3 build.py --serve      # build, then serve at http://localhost:8000
    python3 build.py new git "Undo the last commit"

No third-party dependencies: Python 3.9+ and a checkout is all you need.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import socketserver
import sys
from datetime import date
from pathlib import Path

from tilbuild import content, markdown_lite
from tilbuild.render import SiteBuilder

ROOT = Path(__file__).resolve().parent

NEW_TEMPLATE = """# {title}

{body}
"""


def build(clean: bool = False) -> SiteBuilder:
    config = content.load_config(ROOT)
    output = ROOT / config["output_dir"]
    if clean and output.exists():
        shutil.rmtree(output)
    snippets = content.collect(ROOT, config)
    builder = SiteBuilder(ROOT, config, snippets)
    builder.build()
    print(
        "Built %d snippets across %d topics into %s/"
        % (len(snippets), len(builder.topics), config["output_dir"])
    )
    return builder


def serve(port: int) -> None:
    builder = build()
    directory = str(builder.output)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        print("Serving %s at http://localhost:%d/ (ctrl-c to stop)" % (directory, port))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def new(topic: str, title: str, tags: str | None) -> Path:
    config = content.load_config(ROOT)
    slug = markdown_lite.slugify(title)
    path = ROOT / config["source_dir"] / markdown_lite.slugify(topic) / ("%s.md" % slug)
    if path.exists():
        raise SystemExit("Refusing to overwrite existing snippet: %s" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    front_matter = ""
    if tags:
        front_matter = "---\ntags: %s\ndate: %s\n---\n\n" % (tags, date.today().isoformat())
    path.write_text(
        front_matter + NEW_TEMPLATE.format(title=title, body="Write the snippet here."),
        encoding="utf-8",
    )
    print("Created %s" % path.relative_to(ROOT))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serve", action="store_true", help="serve the built site locally")
    parser.add_argument("--port", type=int, default=8000, help="port for --serve (default 8000)")
    parser.add_argument("--clean", action="store_true", help="delete the output directory first")
    sub = parser.add_subparsers(dest="command")
    new_parser = sub.add_parser("new", help="scaffold a new snippet")
    new_parser.add_argument("topic")
    new_parser.add_argument("title")
    new_parser.add_argument("--tags", help="comma separated tags")

    args = parser.parse_args(argv)
    if args.command == "new":
        new(args.topic, args.title, args.tags)
    elif args.serve:
        serve(args.port)
    else:
        build(clean=args.clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
