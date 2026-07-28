#!/usr/bin/env python3
"""Structural lint for the Masteriyo docs content.

Catches the classes of problem that have actually reached production:

  * frontmatter that a strict YAML front-matter parser cannot read
    (a closing `---` with a trailing space silently broke one page)
  * a page with no title or no excerpt (both are user-visible: the excerpt is
    rendered under the H1, used as the meta description, and is one of only two
    fields the site search indexes)
  * uppercase letters or spaces in a content path or asset path
    (a mixed-case slug produced a page that 502'd while still being listed in
    the sitemap)
  * duplicate numeric prefixes inside a section, which make the sidebar order
    depend on filesystem order
  * `show_child_cards` on a page that has no children, which suppresses
    prev/next navigation and renders an empty card grid

Redirects are NOT configured in this repo: it is consumed as a git submodule at
`content/docs` by the website repo, whose publish root is `.next`, so a
`_redirects` file here is never read. Redirects live in the website repo, in
`next.config.js` and `public/_redirects`.

Run: python3 .github/scripts/lint-docs.py
"""

import os
import re
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)

errors = []
warnings = []


def rel(path):
    return os.path.relpath(path, REPO)


def content_files():
    out = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in {".git", ".github", ".vscode", "node_modules"}]
        for f in files:
            if f.endswith(".mdx"):
                out.append(os.path.join(root, f))
    return sorted(out)


def url_for(path):
    parts = rel(path).split(os.sep)
    seg = [re.sub(r"^\d+-", "", p) for p in parts]
    seg[-1] = re.sub(r"\.mdx$", "", seg[-1])
    if seg[-1] == "index":
        seg = seg[:-1]
    return "/" + "/".join(seg) if seg else "/"


def main():
    files = content_files()
    if not files:
        errors.append("no .mdx files found — is this running from the repo root?")
        return

    urls = set()
    prefixes = defaultdict(list)

    for path in files:
        name = rel(path)
        raw = open(path, encoding="utf-8").read()

        m = FRONTMATTER.match(raw)
        if not m:
            head = raw.split("\n")[:6]
            errors.append(
                f"{name}: frontmatter is not parseable. The file must start with `---` and the "
                f"closing `---` must be on its own line with no trailing whitespace. First lines: {head!r}"
            )
            continue

        fm = {}
        for line in m.group(1).split("\n"):
            if ":" in line and not line.startswith((" ", "\t", "-")):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip("\"'")

        if not fm.get("title"):
            errors.append(f"{name}: missing `title`")
        if not fm.get("excerpt"):
            errors.append(
                f"{name}: missing `excerpt` — it is the page subtitle, the meta description, "
                f"and half of what site search can match on"
            )

        is_index = os.path.basename(path) == "index.mdx"
        if not is_index and "show_child_cards" in fm:
            errors.append(
                f"{name}: `show_child_cards` on a page with no children. It suppresses prev/next "
                f"navigation and renders an empty card grid. Remove the key."
            )

        base = os.path.basename(path)
        if base != base.lower() or " " in name:
            errors.append(
                f"{name}: content paths must be all lowercase with no spaces "
                f"(a mixed-case slug produced a page that returned 502 while still being in the sitemap)"
            )

        pm = re.match(r"^(\d+)-", base)
        if pm and not is_index:
            prefixes[(os.path.dirname(name), pm.group(1))].append(base)

        urls.add(url_for(path))

    for (section, prefix), names in sorted(prefixes.items()):
        if len(names) > 1:
            errors.append(
                f"{section}: duplicate order prefix {prefix}- on {', '.join(sorted(names))} "
                f"— sidebar order becomes non-deterministic"
            )

    for root, dirs, afiles in os.walk(os.path.join(REPO, "assets")):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in afiles:
            if f.startswith("."):
                continue
            p = rel(os.path.join(root, f))
            if " " in p or p != p.lower():
                warnings.append(f"{p}: asset paths should be lowercase with no spaces")

    print(f"checked {len(files)} pages")
    for w in warnings:
        print(f"warning: {w}")
    if errors:
        print()
        for e in errors:
            print(f"error: {e}")
        print(f"\n{len(errors)} error(s)")
        sys.exit(1)
    print("ok")


main()
