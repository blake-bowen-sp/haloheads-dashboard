# Haloheads — Video Multi-Tab Capture & Extraction

- **Date:** 2026-06-16
- **Status:** Approved (via `/goal`)
- **Owner:** Aaron

## Summary

Let a player upload (or shoot on the spot) a ~2-second video that flips through the
in-game post-game **carnage-report tabs** — `OVERVIEW`, `DETAILED STATS`, `MEDALS`,
etc. Gemini (the existing inline path, `gemini-3.5-flash`) reads every tab out of the
video into a generic per-tab structure, and the dashboard renders **one page per
captured tab**.

**One capture = one match = N tabs.** A single photo is just the degenerate case
(one tab). This also fixes a real defect in today's "multiple photos" flow: each tab
photo POSTs separately and can mint duplicate / conflicting match rows for one game.

## Why this design

The post-game report is a horizontal carousel cycled with **RB** (visible as the
`‹ OVERVIEW ›` / `RB` chrome top-right). Each tab shows a *different column set*:

- `OVERVIEW` → `SCORE` `KILLS` `ASSISTS` `DEATHS` (today's only supported view).
- Other tabs → `AVERAGE LIFE` (e.g. `0:58`), `SPREAD` (`+33`, `-11`), medals, accuracy…

Tab names and columns vary by Halo title and gametype, so the schema must be
**dynamic** — Gemini reports whatever tabs/columns it sees; the UI renders them
generically. Nothing about tabs is hard-coded.

## Scope / non-goals (YAGNI)

- **Gemini inline path only** (`app.py` + `haloheads/gemini.py`). The Claude analyzer
  (`scripts/analyze.py`) and the Claude-Code stage/ingest path stay image-only and
  untouched.
- **Both per-match tab pages and career-wide per-tab aggregation** (Aaron: "we want
  both"). Per-match shows one game's tabs; career rolls each extra-tab column up across
  all games. Aggregation rule is generic and transparent: per `(gamertag, tab, column)`
  show the **per-game average** (times like `M:SS` parsed to seconds and re-formatted),
  plus games played — comparable across players regardless of game count.
- Halo Tracker *web page* parsing (`scoreboard.png`) remains out of scope.
- No new model dependency: `gemini-3.5-flash` already handles video.

## Model

`gemini-3.5-flash` — current GA flagship-flash, video-capable, already in use.
Configurable via `GEMINI_MODEL`. `gemini-3.1-pro-preview` is the only thing "newer"
(still Preview); noted as a manual fallback, not wired.

## Data model — dynamic tabs

```json
{
  "is_scoreboard": true, "winning_team": "GREEN", "gametype": "TEAM SLAYER", "map": null,
  "tabs": [
    { "name": "OVERVIEW", "columns": ["SCORE","KILLS","ASSISTS","DEATHS"],
      "players": [ {"gamertag":"Cyborg800","clan_tag":"4039","team":"BLUE",
                    "stats": {"SCORE":250,"KILLS":19,"ASSISTS":5,"DEATHS":4}} ] },
    { "name": "DETAILED STATS", "columns": ["AVERAGE LIFE","SPREAD"],
      "players": [ {"gamertag":"Cyborg800","clan_tag":"4039","team":"BLUE",
                    "stats": {"AVERAGE LIFE":"0:58","SPREAD":33}} ] }
  ]
}
```

- `stats` is a `column → (int | float | str)` map. Times like `0:58` stay strings;
  counts stay ints. **Any tab works with zero new code.**
- **Canonical anchor:** the tab whose columns include SCORE+KILLS+ASSISTS+DEATHS
  (or named `OVERVIEW`) is mapped to the existing `CarnageReport`/`PlayerRow`, so the
  current leaderboard, MVP, K/D, dedup (`game_hash`), and store are **unchanged**.
  Extra tabs are purely additive. A video with no OVERVIEW/SKAD tab → `no_readable_stats`
  (moved to `review/`), exactly like today's zero-stats path.
- Players are merged across tabs by `gamertag` (+ `clan_tag`).

Dataclasses (in `haloheads/schema.py`): `TabPlayer{gamertag, clan_tag, team, stats}`,
`Tab{name, columns, players}`, `MultiTabReport{winning_team, gametype, map, tabs}`.
Helpers: `validate_multitab(dict) -> MultiTabReport`, `canonical_report(multi) ->
CarnageReport`, `tabs_to_dicts(...)` / `overview_tab(report)` (synthesize a single
OVERVIEW tab from a `CarnageReport`, used for image uploads so they render uniformly).

## Extraction (`haloheads/gemini.py`)

- Keep `extract_with_gemini(data) -> CarnageReport` (image path) **unchanged** — the
  app and 4 tests depend on it.
- Add `extract_tabs_from_video(data, mime_type, *, api_key, model) -> MultiTabReport`:
  - **File API** flow: resumable upload (`/upload/v1beta/files`) → poll `files/<id>`
    until `state == ACTIVE` → reference `file_data.file_uri` in `generateContent`.
  - `videoMetadata.fps = 5` (a 2 s flip → ~3 frames/tab so each tab lands a clean
    frame), `mediaResolution = MEDIA_RESOLUTION_HIGH` (small digits stay legible).
  - mime: `video/quicktime` (.mov), `video/mp4`. `responseMimeType=application/json`,
    `temperature=0`, same not-a-scoreboard guard (raise `NotAScoreboard`).
  - Prompt: "this video flips through ONE match's post-game tabs; read each distinct
    tab's name + column headers + every player row; merge players by gamertag."
- `get_report_extractor()` mirrors `extraction.get_extractor()`: returns a **fake**
  multi-tab extractor when `HALOHEADS_FAKE_GEMINI=1` (deterministic E2E, no API key).
  Distinct from the analyzer's `HALOHEADS_FAKE_EXTRACT` so existing E2E is unaffected.

## Upload flow (`app.py`)

- `/upload` accepts image **or** video on the same `image` form field. Branch on
  `file.mimetype`:
  - `video/*` → `extract_tabs_from_video` → `multi`; `report = canonical_report(multi)`;
    `tabs = multi.tabs`.
  - else → `extract_with_gemini` (unchanged); `tabs = [overview_tab(report)]`.
- Inline analysis runs when `GEMINI_API_KEY` is set **or** `HALOHEADS_FAKE_GEMINI=1`.
  All existing status branches (`duplicate_image`, `not_a_scoreboard`,
  `no_readable_stats`, `duplicate_game`, `analyzed`, `analysis_failed`, `stored`) keep
  their behavior.
- `build_docs(..., tabs=tabs)` attaches `match["tabs"]` (JSON). `MAX_CONTENT_LENGTH`
  → **64 MB**.

## Storage

- `LocalStorage` / `GcsStorage`: derive the saved extension from `content_type`
  (`image/jpeg→.jpg`, `image/png→.png`, `video/mp4→.mp4`, `video/quicktime→.mov`;
  default `.jpg`). `list_pending` / `move` handle any media extension.
- `SqliteStore.matches`: add `tabs TEXT` (JSON) via an additive `ALTER TABLE`
  migration; `add_match` writes it (defensive `match.get("tabs")`). New
  `get_match(match_id) -> dict | None` (parses `tabs` JSON) and
  `recent_matches(limit) -> list[dict]`. `FirestoreStore`: `tabs` array field + same
  two methods.
- `build_docs` always emits a `tabs` key (default `None`) so every caller and the
  INSERT stay consistent.

## Aggregation (`haloheads/aggregate.py`)

- `tab_career(matches) -> {tab_name: {"columns": [...], "rows": [{gamertag, games,
  stats: {col: value}}]}}`. For each distinct tab name across all stored matches, group
  tab-player rows by gamertag and, per column, average the numeric values (parse `M:SS`
  → seconds → re-format; skip non-numeric). `OVERVIEW` is excluded (the existing
  leaderboard already covers it). Generic — no per-column hard-coding.

## Dashboard

- `GET /api/matches` → recent matches `{match_id, gametype, map, winning_team,
  uploaded_at, tab_names, players}`.
- `GET /api/match/<id>` → `{...meta, tabs: [...]}`.
- `GET /api/tab-career` → the `tab_career` rollup (career pages per extra tab).
- `templates/dashboard.html`:
  - Upload input `accept="image/*,video/*"` (no `capture` attr → iOS shows
    *Camera (photo **or** video) / Photo Library / Files* = shoot-or-upload). Multi-file
    still works (a video = one file = one match).
  - **Career — By Tab:** one panel per distinct extra tab (e.g. `DETAILED STATS`),
    a generic table of gamertag → averaged columns + games. The headline career view.
  - **Matches:** list recent games; selecting one opens a tab bar whose pages mirror
    that game's in-game tabs, each a generic table from `columns` + per-player `stats`.
  - Matrix theme reused (`.panel`, `table`, `cell()`).

## Verification (per Aaron's testing rules)

- **Unit:** `validate_multitab`; `canonical_report` SKAD detection + cross-tab merge;
  `overview_tab`; sqlite `tabs` round-trip + `get_match`/`recent_matches`; media-extension
  storage (save/list/move a `.mp4`); gemini video request shape (mock the File-API +
  `generateContent` HTTP — assert `file_uri`, `videoMetadata.fps`, `mediaResolution`).
- **Golden (real Gemini, gated on `GEMINI_API_KEY`):** a synthetic multi-tab video →
  assert ≥2 tabs with the right names + exact known per-tab values + correct merge.
  **Semantic-delta:** a second, different video → different stored tabs/values (guards
  against a `return {}` placeholder).
- **E2E (Playwright, `HALOHEADS_FAKE_GEMINI=1`):** open `/` → click the real Upload
  button → select the synthetic `.mp4` through `#up-input` → assert 200 `analyzed` →
  the match appears with multiple tab pages showing the extra-tab columns. Real clicks,
  no `skip`.
- **Fixture:** build the synthetic video with OpenCV/ffmpeg — one fictional game across
  `OVERVIEW` + `DETAILED STATS` tabs with known ground truth — committed under
  `tests/fixtures/` (+ a "book page" non-scoreboard clip for the reject path).

## Deploy

- `gcloud run deploy haloheads --source .` on project `haloheads-dashboard`, ensuring
  **`GEMINI_API_KEY`** is set on the service (Secret Manager ref or `--set-env-vars`)
  and `GEMINI_MODEL` optional. Confirm Cloud Run request-size headroom for ~30–60 MB
  videos.
- Update `README.md` + `.env.example` to document the **Gemini inline path**
  (`GEMINI_API_KEY`, `GEMINI_MODEL`, `HALOHEADS_FAKE_GEMINI`) and the new video/tabs
  feature — currently undocumented.

## Known limitations

- A photo of a *non-OVERVIEW* tab alone yields no leaderboard rows (no SKAD columns) —
  unchanged from today; video always passes through OVERVIEW so it's a non-issue there.
- Career aggregation of extra-tab stats is deferred (columns vary by gametype).
- If `GEMINI_API_KEY` is unset, a video upload is stored but not analyzed (graceful
  degrade), and the image-only Claude analyzer can't process it.
