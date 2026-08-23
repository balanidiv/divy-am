#!/usr/bin/env python3
"""Pull Homepage / Work / Posts from Notion into site-data.json.

Stdlib only. Requires NOTION_TOKEN. Overlays an existing site-data.json so
curated display_role / outcome / dates / url / location / roles survive when
Notion fields are thin. Does not invent metrics.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "site-data.json"

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"

HOMEPAGE_ID = "3c5635ae428881c49643c4d8c1630f1f"
WORK_PAGE_ID = "28b635ae428880ae9a82f68e329d9704"
WORK_DB_ID = "28b635ae42888082ab01c925be084c98"
POSTS_DB_ID = "584f9cce43ae4bfb97eaae5a852a6da3"

AO_WAYBACK = (
    "https://web.archive.org/web/20180808010554/http://aggressivelyorganic.com/"
)

COMPANY_URLS = {
    "care.com": "https://care.com/",
    "care": "https://care.com/",
    "gloco": "https://gloco.ai/",
    "gloco.ai": "https://gloco.ai/",
    "deliverend": "https://deliverend.com/",
    "aggressively organic": AO_WAYBACK,
    "ao": AO_WAYBACK,
}

DEFAULT_TOOLS = [
    "Figma",
    "Cursor",
    "Claude",
    "Spotify",
    "Hermes (Nous)",
    "Granola",
    "Slack",
]

SOURCES = {
    "home": {
        "title": "HOME",
        "url": "https://app.notion.com/p/30f45e37a6c3413bb4276290b6021acc",
        "maps_to": "Workspace root. Parent of Homepage and Posts. Not rendered directly.",
    },
    "homepage": {
        "title": "divy.am Homepage",
        "url": "https://app.notion.com/p/3c5635ae428881c49643c4d8c1630f1f",
        "maps_to": "Intro paragraphs, Education list, Tools note (logo-row is SITE-8, not overwritten).",
    },
    "work_page": {
        "title": "Div’s Work",
        "url": "https://app.notion.com/p/28b635ae428880ae9a82f68e329d9704",
        "maps_to": "Work section container.",
    },
    "work_db": {
        "title": "Div’s Work inline DB",
        "url": "https://app.notion.com/p/28b635ae42888082ab01c925be084c98",
        "collection": "collection://28b635ae-4288-80ea-b04b-000b17320bed",
        "maps_to": "Expandable work rows (Care.com, Gloco.ai, Deliverend, Aggressively Organic).",
    },
    "posts_db": {
        "title": "divy.am Posts",
        "url": "https://app.notion.com/p/584f9cce43ae4bfb97eaae5a852a6da3",
        "collection": "collection://afbb4021-1278-4120-b69e-fceca046cac5",
        "maps_to": "Writing section. Only rows with Published checked. Hello draft is unpublished and excluded.",
    },
}

PLACEHOLDER_RE = re.compile(r"\bXXX\b|\bXX\s+million\b", re.I)
AO_LIVE_RE = re.compile(r"https?://(?:www\.)?aggressivelyorganic\.com/?", re.I)
YEAR_RANGE_RE = r"(\d{4}\s*[–—-]\s*(?:\d{4}|[Pp]resent|[Nn]ow))"


def fail(msg: str, code: int = 1) -> None:
    raise SystemExit(msg)


def token() -> str:
    value = (os.environ.get("NOTION_TOKEN") or "").strip()
    if not value:
        fail(
            "NOTION_TOKEN is missing. Add a GitHub Actions repository secret "
            "named NOTION_TOKEN (Notion internal integration token) and share "
            "Homepage, Div's Work, and Posts with that integration."
        )
    return value


def notion(method: str, path: str, body: dict | None = None) -> dict:
    url = NOTION_API + path
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token()}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        fail(f"Notion API {method} {path} failed: {exc.code} {err}")
    except urllib.error.URLError as exc:
        fail(f"Notion API {method} {path} failed: {exc.reason}")


def paginate_children(block_id: str) -> list[dict]:
    blocks: list[dict] = []
    cursor = None
    while True:
        qs = "?page_size=100"
        if cursor:
            qs += f"&start_cursor={cursor}"
        payload = notion("GET", f"/blocks/{block_id}/children{qs}")
        blocks.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
        if not cursor:
            break
    return blocks


def query_database(database_id: str, filter_obj: dict | None = None) -> list[dict]:
    rows: list[dict] = []
    cursor = None
    while True:
        body: dict = {"page_size": 100}
        if filter_obj is not None:
            body["filter"] = filter_obj
        if cursor:
            body["start_cursor"] = cursor
        payload = notion("POST", f"/databases/{database_id}/query", body)
        rows.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
        if not cursor:
            break
    return rows


def plain_text(rich: list | None) -> str:
    return "".join(span.get("plain_text") or "" for span in (rich or []))


def rewrite_href(href: str) -> str:
    if not href:
        return href
    if AO_LIVE_RE.match(href):
        return AO_WAYBACK
    return href


def company_url(name: str, fallback: str = "") -> str:
    key = re.sub(r"\s+", " ", (name or "").strip().lower())
    key = key.replace("’", "'")
    if key in COMPANY_URLS:
        return COMPANY_URLS[key]
    if "aggressively organic" in key or key == "ao":
        return AO_WAYBACK
    if "gloco" in key:
        return COMPANY_URLS["gloco"]
    if "care" in key:
        return COMPANY_URLS["care.com"]
    if "deliverend" in key:
        return COMPANY_URLS["deliverend"]
    return rewrite_href(fallback) if fallback else ""


def rich_to_html(rich: list | None) -> str:
    parts: list[str] = []
    for span in rich or []:
        text = escape(span.get("plain_text") or "")
        href = span.get("href")
        if not href:
            href = ((span.get("text") or {}).get("link") or {}).get("url")
        if href:
            href = rewrite_href(href)
            text = (
                f'<a href="{escape(href, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">{text}</a>'
            )
        parts.append(text)
    return "".join(parts)


def is_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.search(text or ""))


def block_rich(block: dict) -> list:
    kind = block.get("type") or ""
    payload = block.get(kind) or {}
    if isinstance(payload, dict):
        return payload.get("rich_text") or payload.get("text") or []
    return []


def heading_label(block: dict) -> str:
    kind = block.get("type") or ""
    if kind not in ("heading_1", "heading_2", "heading_3"):
        return ""
    return plain_text(block_rich(block)).strip()


def section_key(text: str) -> str | None:
    t = (text or "").strip().lower()
    if t == "intro" or t.startswith("intro"):
        return "intro"
    if t == "education" or t.startswith("education"):
        return "education"
    if t == "tools" or t.startswith("tools"):
        return "tools"
    return None


def parse_education_line(raw: str) -> dict | None:
    text = " ".join((raw or "").split()).strip()
    if not text or is_placeholder(text):
        return None

    m = re.match(rf"^(.*?)\s+{YEAR_RANGE_RE}\s*[—–]\s*(.+)$", text)
    if m:
        return {
            "label": m.group(1).strip(" ,;"),
            "years": normalize_years(m.group(2)),
            "detail": m.group(3).strip(),
        }
    m = re.match(rf"^(.*?)\s+[—–]\s+(.+?)\s+{YEAR_RANGE_RE}$", text)
    if m:
        return {
            "label": m.group(1).strip(" ,;"),
            "years": normalize_years(m.group(3)),
            "detail": m.group(2).strip(),
        }
    m = re.match(rf"^(.*?)\s+{YEAR_RANGE_RE}$", text)
    if m:
        return {
            "label": m.group(1).strip(" ,;"),
            "years": normalize_years(m.group(2)),
            "detail": "",
        }
    m = re.match(r"^(.*?)\s+[—–]\s+(.+)$", text)
    if m:
        return {
            "label": m.group(1).strip(" ,;"),
            "years": "",
            "detail": m.group(2).strip(),
        }
    return {"label": text, "years": "", "detail": ""}


def normalize_years(value: str) -> str:
    return re.sub(r"\s*[–—-]\s*", "–", (value or "").strip())


def load_existing() -> dict:
    if not DATA_PATH.exists():
        return {}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def name_key(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "").strip().lower())
    n = n.replace("’", "'")
    if n in ("gloco.ai", "gloco"):
        return "gloco"
    if n in ("aggressively organic", "ao"):
        return "ao"
    if n in ("care.com", "care"):
        return "care.com"
    return n


def empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def prop_by_names(props: dict, names: list[str]) -> dict | None:
    lowered = {k.lower(): k for k in props}
    for name in names:
        key = lowered.get(name.lower())
        if key:
            return props[key]
    return None


def prop_plain(prop: dict | None):
    if not prop:
        return ""
    kind = prop.get("type")
    if kind == "title":
        return plain_text(prop.get("title"))
    if kind == "rich_text":
        return plain_text(prop.get("rich_text"))
    if kind == "select":
        return ((prop.get("select") or {}).get("name")) or ""
    if kind == "status":
        return ((prop.get("status") or {}).get("name")) or ""
    if kind == "multi_select":
        return [x.get("name") for x in (prop.get("multi_select") or []) if x.get("name")]
    if kind == "url":
        return prop.get("url") or ""
    if kind == "checkbox":
        return bool(prop.get("checkbox"))
    if kind == "date":
        return prop.get("date")
    if kind == "number":
        return prop.get("number")
    return ""


def format_dates(date_obj: dict | None) -> tuple[str, str | None, str | None]:
    if not date_obj:
        return "", None, None
    start = date_obj.get("start") or ""
    end = date_obj.get("end")
    date_start = start[:10] if start else None
    date_end = end[:10] if end else None

    def month_year(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso[:10])
        except ValueError:
            return iso
        return dt.strftime("%b %Y")

    if not date_start:
        return "", None, None
    left = month_year(date_start)
    right = month_year(date_end) if date_end else "present"
    return f"{left}–{right}", date_start, date_end


def notion_url(page: dict) -> str:
    page_id = (page.get("id") or "").replace("-", "")
    if page_id:
        return f"https://app.notion.com/p/{page_id}"
    return page.get("url") or ""


def pull_homepage() -> tuple[list[dict], list[dict]]:
    blocks = paginate_children(HOMEPAGE_ID)
    buckets: dict[str, list[dict]] = {"intro": [], "education": [], "tools": []}
    current = "intro"
    for block in blocks:
        label = heading_label(block)
        if label:
            key = section_key(label)
            if key:
                current = key
            continue
        if current == "tools":
            continue
        kind = block.get("type")
        if current == "intro":
            if kind == "paragraph":
                html = rich_to_html(block_rich(block)).strip()
                text = plain_text(block_rich(block)).strip()
                if html and not is_placeholder(text):
                    buckets["intro"].append({"html": html})
        elif current == "education":
            if kind in ("paragraph", "bulleted_list_item", "numbered_list_item"):
                text = plain_text(block_rich(block)).strip()
                row = parse_education_line(text)
                if row:
                    buckets["education"].append(row)
    return buckets["intro"], buckets["education"]


def body_from_blocks(blocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    pending_items: list[str] = []

    def flush_list() -> None:
        nonlocal pending_items
        if pending_items:
            out.append({"type": "ul", "items": pending_items})
            pending_items = []

    for block in blocks:
        kind = block.get("type")
        text = plain_text(block_rich(block)).strip()
        html = rich_to_html(block_rich(block)).strip()
        if kind == "paragraph":
            flush_list()
            if html and not is_placeholder(text):
                out.append({"type": "p", "html": html})
        elif kind in ("bulleted_list_item", "numbered_list_item"):
            if html and not is_placeholder(text):
                pending_items.append(html)
        else:
            flush_list()
    flush_list()
    return out


def extract_work_row(page: dict, existing_by_key: dict) -> dict:
    props = page.get("properties") or {}
    title = prop_plain(prop_by_names(props, ["Name", "Company", "Title"])) or ""
    if isinstance(title, list):
        title = " ".join(str(x) for x in title)
    company_prop = prop_plain(prop_by_names(props, ["Company", "Name"]))
    if isinstance(company_prop, list):
        company_prop = " ".join(str(x) for x in company_prop)
    name = (company_prop or title or "").strip()
    # Prefer a value that looks like a company if both exist.
    title_key = name_key(title)
    company_key = name_key(str(company_prop or ""))
    if company_key in COMPANY_URLS or company_key in ("gloco", "ao", "care.com", "deliverend"):
        name = str(company_prop).strip()
    elif title_key in COMPANY_URLS or title_key in ("gloco", "ao", "care.com", "deliverend"):
        name = title.strip()

    notion_title = prop_plain(
        prop_by_names(props, ["Role", "Title", "Position", "Job", "notion_title"])
    )
    if isinstance(notion_title, list):
        notion_title = ", ".join(str(x) for x in notion_title)
    notion_title = (notion_title or title or "").strip()

    display_role = prop_plain(prop_by_names(props, ["Display role", "Display Role", "Role"]))
    if isinstance(display_role, list):
        display_role = ", ".join(str(x) for x in display_role)
    display_role = (display_role or "").strip()

    outcome = prop_plain(prop_by_names(props, ["Outcome", "Result", "Impact"]))
    if isinstance(outcome, list):
        outcome = ", ".join(str(x) for x in outcome)
    outcome = (outcome or "").strip()

    location = prop_plain(prop_by_names(props, ["Location", "Place"]))
    if isinstance(location, list):
        location = ", ".join(str(x) for x in location)
    location = (location or "").strip()

    roles = prop_plain(prop_by_names(props, ["Roles", "Tags", "Function"]))
    if isinstance(roles, str):
        roles = [roles] if roles else []
    elif not isinstance(roles, list):
        roles = []

    url_prop = prop_plain(prop_by_names(props, ["URL", "Url", "Website", "Link", "Company URL"]))
    if isinstance(url_prop, list):
        url_prop = url_prop[0] if url_prop else ""
    url_prop = rewrite_href((url_prop or "").strip())
    url = company_url(name, url_prop)

    date_prop = prop_plain(prop_by_names(props, ["Date", "Dates", "Time"]))
    dates, date_start, date_end = format_dates(date_prop if isinstance(date_prop, dict) else None)

    body = body_from_blocks(paginate_children(page["id"]))

    row = {
        "name": name,
        "url": url,
        "notion_url": notion_url(page),
        "notion_title": notion_title,
        "display_role": display_role,
        "outcome": outcome,
        "dates": dates,
        "date_start": date_start,
        "date_end": date_end,
        "location": location,
        "roles": roles,
        "body": body,
    }

    prev = existing_by_key.get(name_key(name))
    if prev:
        for field in ("display_role", "outcome", "dates", "url", "location", "roles"):
            if empty(row.get(field)) and not empty(prev.get(field)):
                row[field] = prev[field]
        for field in ("date_start", "date_end", "notes"):
            if empty(row.get(field)) and not empty(prev.get(field)):
                row[field] = prev[field]
        if empty(row.get("name")) and prev.get("name"):
            row["name"] = prev["name"]
        if not row.get("url"):
            row["url"] = company_url(prev.get("name") or name, prev.get("url") or "")
        # Always enforce AO Wayback / mapped company hrefs.
        forced = company_url(row.get("name") or name, row.get("url") or "")
        if forced:
            row["url"] = forced
    return row


def pull_work(existing: dict) -> list[dict]:
    existing_by_key = {name_key(job.get("name") or ""): job for job in existing.get("work") or []}
    pages = query_database(WORK_DB_ID)
    rows = []
    for page in pages:
        row = extract_work_row(page, existing_by_key)
        if row.get("name"):
            rows.append(row)
    return rows


def extract_post(page: dict, published: bool) -> dict:
    props = page.get("properties") or {}
    title = prop_plain(prop_by_names(props, ["Title", "Name"])) or ""
    if isinstance(title, list):
        title = " ".join(str(x) for x in title)
    slug = prop_plain(prop_by_names(props, ["Slug"]))
    if isinstance(slug, list):
        slug = slug[0] if slug else ""
    summary = prop_plain(prop_by_names(props, ["Summary", "Description", "Excerpt"]))
    if isinstance(summary, list):
        summary = " ".join(str(x) for x in summary)
    date_prop = prop_plain(prop_by_names(props, ["Date", "Published Date", "Posted"]))
    date = ""
    if isinstance(date_prop, dict):
        date = (date_prop.get("start") or "")[:10]
    elif isinstance(date_prop, str):
        date = date_prop[:10]
    pub = prop_plain(prop_by_names(props, ["Published"]))
    if isinstance(pub, bool):
        published = pub
    post = {
        "title": (title or "").strip(),
        "slug": (slug or "").strip(),
        "summary": (summary or "").strip(),
        "date": date,
        "published": bool(published),
        "url": notion_url(page),
    }
    if not published:
        post["reason"] = "Published is unchecked. Must not appear on the site."
    return post


def pull_posts() -> tuple[list[dict], list[dict]]:
    published_pages = query_database(
        POSTS_DB_ID,
        {"property": "Published", "checkbox": {"equals": True}},
    )
    unpublished_pages = query_database(
        POSTS_DB_ID,
        {"property": "Published", "checkbox": {"equals": False}},
    )
    published = []
    for page in published_pages:
        post = extract_post(page, True)
        if post["title"].strip().lower() == "hello" and not post["published"]:
            continue
        if post["published"]:
            published.append(post)
    excluded = []
    for page in unpublished_pages:
        post = extract_post(page, False)
        if post["title"].strip().lower() == "hello" or not post["published"]:
            post["published"] = False
            post["reason"] = "Published is unchecked. Must not appear on the site."
            excluded.append(post)
    return published, excluded


def now_stamps() -> tuple[str, str]:
    utc = datetime.now(timezone.utc).replace(microsecond=0)
    ct = utc.astimezone(ZoneInfo("America/Chicago"))
    pulled_at = utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    pulled_at_ct = ct.strftime("%Y-%m-%d %I:%M %p CT").lstrip()
    pulled_at_ct = re.sub(r" 0(\d:)", r" \1", pulled_at_ct)
    return pulled_at, pulled_at_ct


def main() -> int:
    existing = load_existing()
    intro, education = pull_homepage()
    work = pull_work(existing)
    posts_published, posts_excluded = pull_posts()

    tools_note = existing.get("tools_note")
    if not tools_note:
        tools_note = list(DEFAULT_TOOLS)

    pulled_at, pulled_at_ct = now_stamps()
    data = {
        "pulled_at": pulled_at,
        "pulled_at_ct": pulled_at_ct,
        "pulled_via": "GitHub Action + Notion API",
        "note": (
            "Live on Railway (https://divy.am/). Tab title is Div Balani. "
            "Logo-row is SITE-8 and is not regenerated from this file."
        ),
        "sources": SOURCES,
        "intro": intro,
        "tools_note": tools_note,
        "education": education,
        "work": work,
        "posts_published": posts_published,
        "posts_excluded": posts_excluded,
    }

    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("pull-from-notion.py")
    print(f"  wrote {DATA_PATH}")
    print(f"  pulled_at     {pulled_at}")
    print(f"  pulled_at_ct  {pulled_at_ct}")
    print(f"  intro         {len(intro)}")
    print(f"  education     {len(education)}")
    print(f"  work          {len(work)}")
    print(f"  posts_pub     {len(posts_published)}")
    print(f"  posts_excl    {len(posts_excluded)}")
    skipped = "Hello draft unpublished" if any(
        (p.get("title") or "").lower() == "hello" for p in posts_excluded
    ) else "no Hello draft in excluded"
    print(f"  drafts        {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
