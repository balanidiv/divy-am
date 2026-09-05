# Sync divy.am preview from Notion

Preview only. This does **not** go live. Title stays Principal PM. One CMS: Notion. No Ghost, no second store.

## Pages he edits

| He edits | URL | Site section |
| --- | --- | --- |
| **divy.am Homepage** | https://app.notion.com/p/3c5635ae428881c49643c4d8c1630f1f | Intro paragraphs, Education. Tools heading is a note — the visible logo row is SITE-8 and is not overwritten. |
| **Div's Work** (page + inline DB) | https://app.notion.com/p/28b635ae428880ae9a82f68e329d9704 | Expandable Work rows (career jobs). Collection `collection://28b635ae-4288-80ea-b04b-000b17320bed`. Company pages: Care.com, Gloco.ai, Deliverend, Aggressively Organic. |
| **divy.am Tinkerings** | https://app.notion.com/p/b1410e89913e4f67a1971f82798f1542 | Tinkerings section (shipped utilities, not career jobs). Collection `collection://0402327e-c17a-438f-bfb8-9268e85dcd34`. **Only `Published` checked rows render.** Connect via Add connections. |
| **divy.am Posts** | https://app.notion.com/p/584f9cce43ae4bfb97eaae5a852a6da3 | Writing. Collection `collection://afbb4021-1278-4120-b69e-fceca046cac5`. Fields: Title, Slug, Date, Published, Summary. **Only `Published` checked rows render.** |
| HOME (parent, do not treat as copy) | https://app.notion.com/p/30f45e37a6c3413bb4276290b6021acc | Workspace root that holds Homepage + Posts. |

Draft **Hello** (`/hello`, Published off) must never appear.

## How a refresh works

1. Edit the Notion pages above.
2. An agent pulls via Notion MCP (`user-Notion`: `notion-search`, `notion-fetch`, `notion-query-data-sources`) and overwrites `site-data.json`.
3. Run `python3 rebuild.py` in this folder. It renders intro / work / education / published posts into `index.html` and **leaves the SITE-8 logo-row untouched**.
4. Copy the changed files to `/Users/divyambalani/divy-am-preview/` and reload http://127.0.0.1:4173

`rebuild.py` does **not** call the Notion API. There is no integration token on this Mac static preview. If `site-data.json` is missing it exits and prints that an agent must pull via MCP first.

## Honest wiring

**Wired (this snapshot)**

- Intro, Education, Work, and Projects come from Notion pulls, stored in `site-data.json`, then rendered by `rebuild.py`.
- Work = career jobs (Care.com, Gloco.ai, Deliverend, Aggressively Organic). Tinkerings = shipped utilities (foto). Tinkerings pull requires Notion integration connected to divy.am Tinkerings DB.
- Posts query is live: zero published rows. Hello is recorded in `posts_excluded` and is not rendered.
- Care.com / Gloco / Deliverend / AO metrics are only those already in Notion (or already verified on the page). Placeholders `XXX` / `XX` million were omitted, not filled in.
- AO company href stays the Wayback URL, not a live `aggressivelyorganic.com`. Missing-from-Notion WISH-TV + Wayback links were kept from the verified set. IndyStar was added because it is in the Notion AO body.

**Still baked**

- Chassis A (serif, 36rem, face, expandable work, theme toggle, footer, JSON-LD, `<title>` Principal PM).
- SITE-8 logo row (Figma, Cursor, Claude, Spotify, Hermes, Granola, Slack). Rebuild will not rewrite it even if Homepage → Tools changes.
- Outcome one-liners and display roles (`Principal PM`, `Head of Product, co-founder`, `27M seekers, six marketplaces`, …) are curated into `site-data.json` from Notion fields + body — they are not a raw property dump.
- The Mac `python3 -m http.server` on 127.0.0.1:4173 is a static file server. It cannot call Notion MCP. Saving a Notion page does nothing to the preview until someone re-pulls and rebuilds.

**Blocker for automatic self-serve refresh**

A host-side Notion integration token (and a small fetch job that writes `site-data.json`) is required before “edit Notion → site updates itself.” MCP only works when an agent is in this session. Do not put a token in the static preview folder.

## Go-live sequence (Firstmate — do not execute)

Not this ticket. When he is ready:

1. Put this preview in a GitHub repo (static files + `rebuild.py` + `site-data.json`).
2. Host on Vercel (or equivalent). Optional later: a serverless refresh that uses a Notion integration token to rewrite `site-data.json` and rebuild.
3. Point `divy.am` DNS off Framer / GoDaddy to that host.
4. Keep Title = Principal PM. Do not add Weaponized or a second CMS.

Until then the public site stays as-is. Preview: http://127.0.0.1:4173
