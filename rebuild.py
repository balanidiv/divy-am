#!/usr/bin/env python3
"""Render index.html from site-data.json. Does not call the Notion API.

This preview host has no Notion integration token. A live refresh is:

  1. Edit Notion (Homepage / Div's Work / Posts).
  2. An agent pulls via Notion MCP (user-Notion: notion-search,
     notion-fetch, notion-query-data-sources) and overwrites site-data.json.
  3. Run: python3 rebuild.py

Mac `python3 -m http.server` cannot talk to Notion MCP. Automatic
self-serve refresh needs a Notion integration token on the host, plus
a fetch step that writes site-data.json.

The SITE-8 logo-row is preserved byte-for-byte and is never regenerated.

Rebuild only replaces intro / work / education / writing. Footer, head,
title, the hero chrome (portrait + right-aligned sun/moon toggle, name +
right-aligned socials), and My Toolbox heading are left alone so a Notion
rebuild cannot move the toggle or X/LinkedIn/Email/Resume back into the footer.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site-data.json"
HTML = ROOT / "index.html"

LOGO_RE = re.compile(r'<div class="logo-row"[^>]*>.*?</div>', re.S)
INTRO_RE = re.compile(
    r'(<div class="space-y-3">)(.*?)(</div>)',
    re.S,
)
PROJECTS_RE = re.compile(
    r'(<ul class="flex flex-col gap-2 list-none p-0 m-0 projects-list">)(.*?)(</ul>\s*</section>)',
    re.S,
)
WORK_RE = re.compile(
    r'(<ul class="flex flex-col gap-2 list-none p-0 m-0 work-list">)(.*?)(</ul>\s*</section>)',
    re.S,
)
EDU_RE = re.compile(
    r'(<h2 id="education-heading">Education</h2>\s*'
    r'<ul class="flex flex-col gap-4 list-none p-0 m-0">)(.*?)(</ul>)',
    re.S,
)
WRITING_RE = re.compile(
    r'\n\s*<section class="space-y-4" id="writing"[^>]*>.*?</section>',
    re.S,
)
WORK_SECTION_RE = re.compile(
    r'(<section class="(?:space-y-4|section-stack)" id="work"[^>]*>.*?</section>)',
    re.S,
)


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def render_body(blocks: list) -> str:
    parts: list[str] = []
    for block in blocks:
        kind = block.get("type")
        if kind == "p":
            parts.append(f"                <p>{block['html']}</p>")
        elif kind == "ul":
            items = "\n".join(f"<li>{item}</li>" for item in block["items"])
            parts.append(f"                <ul>\n{items}\n</ul>")
        else:
            raise SystemExit(f"unknown body block type: {kind}")
    return "\n".join(parts)


def render_work(jobs: list) -> str:
    lis = []
    for job in jobs:
        body = render_body(job["body"])
        lis.append(
            "          <li>\n"
            "            <details>\n"
            "              <summary>\n"
            '                <span class="caret" aria-hidden="true"></span>\n'
            '                <span class="work-main">\n'
            f'                  <span class="work-title"><a href="{job["url"]}" '
            f'target="_blank" rel="noopener noreferrer">{job["name"]}</a> '
            f'<span class="work-role">{job["display_role"]}</span></span>\n'
            f'                  <span class="work-outcome">{job["outcome"]}</span>\n'
            "                </span>\n"
            f'                <span class="work-meta">{job["dates"]}</span>\n'
            "              </summary>\n"
            f'              <div class="work-body">\n{body}\n'
            "              </div>\n"
            "            </details>\n"
            "          </li>"
        )
    return "\n" + "\n".join(lis) + "\n        "


def render_projects(projects: list) -> str:
    lis = []
    for proj in projects:
        body = render_body(proj["body"])
        lis.append(
            "          <li>\n"
            "            <details>\n"
            "              <summary>\n"
            '                <span class="caret" aria-hidden="true"></span>\n'
            '                <span class="work-main">\n'
            f'                  <span class="work-title"><a href="{proj["url"]}" '
            f'target="_blank" rel="noopener noreferrer">{proj["name"]}</a> '
            f'<span class="work-role">{proj["display_role"]}</span></span>\n'
            f'                  <span class="work-outcome">{proj["outcome"]}</span>\n'
            "                </span>\n"
            f'                <span class="work-meta">{proj["dates"]}</span>\n'
            "              </summary>\n"
            f'              <div class="work-body">\n{body}\n'
            "              </div>\n"
            "            </details>\n"
            "          </li>"
        )
    return "\n" + "\n".join(lis) + "\n        "


def render_intro(paragraphs: list) -> str:
    ps = []
    for para in paragraphs:
        ps.append(f"          <p>\n            {para['html']}\n          </p>")
    return "\n" + "\n".join(ps) + "\n        "


def render_education(rows: list) -> str:
    lis = []
    for row in rows:
        years = row.get("years") or ""
        detail = row.get("detail") or ""
        if years and detail:
            lis.append(
                '          <li class="flex flex-col md:flex-row md:items-baseline '
                'md:justify-between md:gap-4">\n'
                '            <div class="flex items-baseline gap-2 flex-wrap">\n'
                f"              <span>{row['label']}</span>\n"
                f'              <span class="text-sm text-[#1a180f]/30 '
                f'dark:text-[#ece9e3]/30 flex-shrink-0">{years}</span>\n'
                "            </div>\n"
                f'            <span class="text-sm text-[#1a180f]/60 '
                f'dark:text-[#ece9e3]/60 md:text-right flex-shrink-0">{detail}</span>\n'
                "          </li>"
            )
        else:
            right = years or detail
            lis.append(
                '          <li class="flex flex-col md:flex-row md:items-baseline '
                'md:justify-between md:gap-4">\n'
                f"            <span>{row['label']}</span>\n"
                f'            <span class="text-sm text-[#1a180f]/60 '
                f'dark:text-[#ece9e3]/60 md:text-right flex-shrink-0">{right}</span>\n'
                "          </li>"
            )
    return "\n" + "\n".join(lis) + "\n        "


def render_writing(posts: list) -> str:
    if not posts:
        return ""
    lis = []
    for post in posts:
        slug = post.get("slug") or ""
        href = f"./{slug}" if slug else "#"
        date = post.get("date") or ""
        summary = post.get("summary") or ""
        lis.append(
            '          <li class="flex flex-col gap-1">\n'
            f'            <a href="{href}">{post["title"]}</a>\n'
            + (f'            <span class="text-sm text-[#1a180f]/45 dark:text-[#ece9e3]/45">{date}</span>\n' if date else "")
            + (f"            <p>{summary}</p>\n" if summary else "")
            + "          </li>"
        )
    items = "\n".join(lis)
    return (
        "\n\n      <section class=\"space-y-4\" id=\"writing\" "
        "aria-labelledby=\"writing-heading\">\n"
        "        <h2 id=\"writing-heading\">Writing</h2>\n"
        '        <ul class="flex flex-col gap-4 list-none p-0 m-0">\n'
        f"{items}\n"
        "        </ul>\n"
        "      </section>"
    )


def sub_one(pattern: re.Pattern, html: str, inner: str, label: str) -> str:
    new, n = pattern.subn(lambda m: m.group(1) + inner + m.group(3), html, count=1)
    if n != 1:
        raise SystemExit(f"failed to replace {label} (matches={n})")
    return new


def main() -> int:
    print("rebuild.py: no Notion API token on this host.")
    print("Expect an agent to pull via Notion MCP and write site-data.json,")
    print("then re-run this script to render index.html.")
    print("SITE-8 logo-row is preserved and not regenerated.")
    if not DATA.exists():
        eprint(f"missing {DATA}")
        return 1
    data = json.loads(DATA.read_text(encoding="utf-8"))
    html = HTML.read_text(encoding="utf-8")
    logo = LOGO_RE.search(html)
    if not logo:
        raise SystemExit("logo-row not found; refusing to write")
    logo_html = logo.group(0)

    html = sub_one(INTRO_RE, html, render_intro(data["intro"]), "intro")
    
    projects = sorted(data.get("projects") or [], key=lambda proj: (
        (proj.get("date_start") or "").strip()
        or (proj.get("date_end") or "").strip()
        or ("9999-12-31" if "present" in (proj.get("dates") or "").lower() or "now" in (proj.get("dates") or "").lower() else "0000-00-00")
    ), reverse=True)
    if projects and PROJECTS_RE.search(html):
        html = sub_one(PROJECTS_RE, html, render_projects(projects), "projects")
    
    work = sorted(data.get("work") or [], key=lambda job: (
        (job.get("date_start") or "").strip()
        or (job.get("date_end") or "").strip()
        or ("9999-12-31" if "present" in (job.get("dates") or "").lower() or "now" in (job.get("dates") or "").lower() else "0000-00-00")
    ), reverse=True)
    html = sub_one(WORK_RE, html, render_work(work), "work")
    html = sub_one(EDU_RE, html, render_education(data["education"]), "education")

    html = WRITING_RE.sub("", html)
    writing = render_writing(data.get("posts_published") or [])
    if writing:
        html, n = WORK_SECTION_RE.subn(lambda m: m.group(1) + writing, html, count=1)
        if n != 1:
            raise SystemExit("failed to insert writing section")

    after = LOGO_RE.search(html)
    if not after or after.group(0) != logo_html:
        html = LOGO_RE.sub(logo_html, html, count=1)
        print("logo-row drifted during render; restored original SITE-8 markup.")
    else:
        print("logo-row unchanged.")

    footer_m = re.search(r"<footer\b.*?</footer>", html, re.S)
    footer_html = footer_m.group(0) if footer_m else ""
    if 'id="theme-toggle"' in footer_html:
        raise SystemExit("theme toggle must stay on the portrait line; found in footer")
    if 'id="theme-toggle"' not in html:
        raise SystemExit("theme toggle missing after rebuild")
    if "social-row" not in html or "hero-name-row" not in html:
        raise SystemExit("name+socials row missing after rebuild")
    if "social-row" in footer_html or "Resume" in footer_html:
        raise SystemExit("socials/Resume must stay on the name line; found in footer")
    if "hero-ident" not in html:
        raise SystemExit("portrait+toggle row missing after rebuild")
    if "theme-icon-sun" not in html or "theme-icon-moon" not in html:
        raise SystemExit("sun/moon theme icons missing after rebuild")
    if html.find("div-portrait.jpg") > html.find('id="theme-toggle"'):
        raise SystemExit("toggle must sit to the right of the portrait on the same line")
    if html.find("<h1") > html.find('class="social-row'):
        raise SystemExit("social-row must sit on the same line as the name")
    if html.find('class="social-row') > html.find('class="space-y-3"'):
        raise SystemExit("social-row must stay above the intro")
    if "My Toolbox" not in html or "toolbox-heading" not in html:
        raise SystemExit("My Toolbox heading missing after rebuild")
    if "chrome-critical" not in html or "styles.css?v=23b" not in html:
        raise SystemExit("critical chrome CSS / cache-bust missing after rebuild")
    if "1cUJ8cGwihEbyEVqy46okNAMeiOpWa98U" not in html:
        raise SystemExit("Drive resume href missing after rebuild")
    if "<title>Div Balani</title>" not in html:
        raise SystemExit("title must stay Div Balani")

    HTML.write_text(html, encoding="utf-8")
    print(f"wrote {HTML} from {DATA}")
    print("theme-toggle (sun/moon) on portrait line; social-row on name line.")
    excluded = data.get("posts_excluded") or []
    if excluded:
        titles = ", ".join(p.get("title", "?") for p in excluded)
        print(f"excluded unpublished drafts: {titles}")
    pub = data.get("posts_published") or []
    print(f"published posts rendered: {len(pub)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
