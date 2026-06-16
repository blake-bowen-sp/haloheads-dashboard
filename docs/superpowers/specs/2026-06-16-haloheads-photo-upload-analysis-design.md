# Haloheads Stats — Photo Upload + On-Demand Analysis

- **Date:** 2026-06-16
- **Status:** Design (pending spec review)
- **Owner:** Aaron (uses), Blake (deploys GCP)

## Summary

Add photo-upload and AI stats extraction to the Haloheads dashboard, staying on
Google Cloud. The work splits into three independent pieces:

1. **Collector** — a thin web app (deployed to Cloud Run by Blake) where anyone
   can upload a photo of the in-game post-game carnage report while playing.
   It only stores the photo. No analysis, no AI on the server.
2. **Analyzer** — a local script in this repo, run on demand by Aaron (or by
   Claude Code on Aaron's instruction). It pulls every un-analyzed upload,
   extracts stats with Claude vision (local `ANTHROPIC_API_KEY` — **no Vertex**),
   and writes the results to Firestore.
3. **Dashboard** — the existing dashboard (served by the collector app), now
   reading aggregated stats from Firestore.

Analysis is deliberately **not** automatic. The dashboard data changes only when
the analyzer is run.

## Goals

- Anyone playing can one-tap upload a carnage-report photo from their phone
  (iOS camera or photo library) with no login and no typing.
- A repeatable local script analyzes everything uploaded and updates the
  dashboard data in one shot.
- Track every player's stats by in-game gamertag across all uploaded matches,
  powering the ranking views in `dashboardideas.md`.
- Replace the fragile OCR + regex extraction with Claude vision returning
  validated structured JSON.

## Non-goals (YAGNI)

- **No Vertex AI.** Claude is called from the local analyzer with an Anthropic
  API key.
- No automatic or real-time analysis.
- No login / accounts (tracking is by gamertag parsed from the image).
- No native iOS app — PWA web app only.
- Halo Tracker web-page parsing (per-player session view) is deferred. v1's only
  supported format is the in-game post-game carnage report.
- "Most improved over time" is a fast-follow, not in v1.

## Primary input: the post-game carnage report

The format is the in-game MCC post-game scoreboard
(`gameStatsImageFiles/testTeamResultData.jpeg`):

- **Header:** `<BLUE|RED> TEAM WON` plus a gametype string (e.g.
  `LEGENDARY SLAYER BR`).
- **Up to 8 player rows** across two teams (team identified by row color),
  each with: clan tag (e.g. `[UNSC]`), gamertag, **SCORE**, **KILLS**,
  **ASSISTS**, **DEATHS**.
- **Map name is frequently absent** from this screen, so it is optional —
  extracted if visible, otherwise blank. An optional free-text "map" field on
  the upload form can fill it.

> This switches the primary format away from the earlier "Halo Tracker web page"
> choice, based on Aaron's description ("upload a photo of the post-game carnage
> reports, that screen"). The carnage report fits the snap-while-playing
> workflow and supplies team, win/loss, and score — which power MVP-per-team and
> win-rate views that the Halo Tracker matches view could not.

## Architecture

```
 Phone (PWA, iOS camera/library)
        │  POST /upload  (image + optional map)
        ▼
 ┌──────────────────────────┐         ┌─────────────────────────────┐
 │ COLLECTOR (Cloud Run)    │  put    │ Cloud Storage bucket        │
 │  GET  /upload  (PWA)     │ ──────► │   pending/<uuid>.jpg        │
 │  POST /upload            │         │   analyzed/<uuid>.jpg       │
 │  GET  /  (dashboard)     │         └─────────────────────────────┘
 │  GET  /api/*             │                 ▲           │
 └──────────┬───────────────┘                 │ list+get  │ move
            │ read                             │           ▼
            ▼                          ┌─────────────────────────────┐
 ┌──────────────────────────┐  write   │ ANALYZER (local script)     │
 │ Firestore                │ ◄─────── │  scripts/analyze.py         │
 │  matches / player_stats  │          │  Claude vision (API key)    │
 └──────────────────────────┘          └─────────────────────────────┘
```

All cloud resources live in one GCP project (Blake's). The only non-GCP
dependency is the Anthropic API, called exclusively from the local analyzer.

### A. Collector (deployed, Cloud Run)

- `GET /upload` — PWA upload page. The control is
  `<input type="file" accept="image/*">` with **no `capture` attribute**, so iOS
  shows the native *Take Photo / Photo Library / Choose File* sheet. Includes an
  optional free-text "map" field, an image thumbnail preview, and upload
  progress. Ships a PWA manifest + service worker + apple-touch-icon so it
  installs to the home screen.
- `POST /upload` — accepts a multipart image (+ optional map), writes it to
  `gs://<bucket>/pending/<uuid>.jpg` with object metadata
  (`uploaded_at`, optional `map`, optional `uploader` label). Returns `200`.
  Performs **no** analysis.
- `GET /` — dashboard; reads Firestore.
- `GET /api/leaderboard`, `/api/player/<gamertag>`, `/api/mvps`,
  `/api/gametypes` — read-time aggregations from Firestore.
- `GET /health`.
- The collector never imports the Anthropic SDK and holds no Anthropic key.

### B. Analyzer (local script, on demand)

`scripts/analyze.py`, a CLI:

1. Lists `gs://<bucket>/pending/`. Flags: `--all` (re-analyze everything),
   `--image <path>` (analyze one local file), `--dry-run` (print extracted JSON,
   write nothing), `--limit N`.
2. For each new image: download bytes, optional Pillow downscale, call Claude
   (Anthropic Messages API, vision) constrained to a strict JSON tool schema.
3. Validate the JSON; compute derived fields (per-player `result` from the
   winning team; K/D).
4. Dedup via image content hash and per-row hash; skip anything already stored.
5. Write one `matches` doc + N `player_stats` docs to Firestore.
6. Move the image `pending/` → `analyzed/` (copy then delete) so later runs skip
   it; on extraction failure move to `failed/` and log.
7. Print a summary: images analyzed, matches added, player rows written,
   gamertags touched.

**Auth:** GCP Application Default Credentials (read bucket, write Firestore,
move objects) + `ANTHROPIC_API_KEY` in the environment.

### C. Dashboard (part of the collector app)

Reads Firestore at request time, computes rankings in-process (data volume is
small — a friend group's matches), and renders the existing matrix-themed
leaderboard plus per-gametype bests and per-match MVPs. Reflects new data as
soon as the analyzer has run.

## Data model (Firestore)

- **`matches`** — one per uploaded carnage report:
  `{ match_id, gametype, map?, winning_team: "BLUE"|"RED", source_image,
     uploaded_at, analyzed_at, image_hash }`
- **`player_stats`** — one per player per match:
  `{ match_id, gamertag, clan_tag?, team: "BLUE"|"RED", result: "WON"|"LOST",
     score, kills, assists, deaths, gametype, map?, created_at, row_hash }`
- **Dedup:** `image_hash` on `matches` (skip a re-uploaded image wholesale);
  `row_hash = sha256(match_id|gamertag|score|kills|assists|deaths)`.
- **Rankings (read-time):**
  - *Leaderboard:* group `player_stats` by `gamertag` → sum kills/deaths/
    assists/score, games, wins → net K/D and win rate.
  - *MVP per team per match:* max `score` within `(match_id, team)`.
  - *Best per gametype:* group by `(gamertag, gametype)`.
  - *Best per map:* group by `(gamertag, map)` where `map` is present.

## Claude extraction

- **Model:** a current Sonnet-class Claude model (cost/accuracy balance),
  configurable via env. Called with the Anthropic Python SDK (`anthropic`),
  Messages API, with the screenshot as an image block.
- **Structured output** forced via a tool `record_carnage_report` whose input
  schema is:
  ```json
  {
    "winning_team": "BLUE | RED",
    "gametype": "string",
    "map": "string | null",
    "players": [
      { "gamertag": "string", "clan_tag": "string|null",
        "team": "BLUE | RED", "score": 0, "kills": 0,
        "assists": 0, "deaths": 0 }
    ]
  }
  ```
- **Prompt** instructs the model to: read team from row color, keep clan tag
  separate from gamertag, ignore the local player's highlighted-row chrome,
  return integers, and emit `null` for map when not shown.
- **Failure handling:** unreadable image or zero players → log, move image to
  `failed/`, continue.

## Verification (per Aaron's testing rules)

- **Unit:** JSON-schema validation; derived-field math (`result` from
  `winning_team`, K/D); dedup hashing — against committed fixtures.
- **Semantic-delta test** (the poker-solver rule): assert the analyzer's output
  for `testTeamResultData.jpeg` contains the *real* gamertags and *exact* stats
  (e.g. `Cyborg800` score 250 / kills 19 / assists 5 / deaths 4;
  `X Jack X7282` 16 kills; winning team `BLUE`) — not a constant. Two different
  inputs must yield different stored rows.
- **Golden integration test:** run real Claude extraction on
  `gameStatsImageFiles/testTeamResultData.jpeg` and assert all 8 players + exact
  K/A/D/score + `winning_team = BLUE`. Gated behind `ANTHROPIC_API_KEY`. This is
  the canonical "does it actually read the image" check.
- **Firestore:** use the Firestore emulator for write/read tests; a dedup test
  re-analyzes the same image and asserts no new documents.
- **Playwright E2E:** drive the collector locally — open `/upload`, upload
  `testTeamResultData.jpeg` through the real file input, assert `200` and that
  the object lands in the (emulated/local) bucket; run the analyzer; load `/`
  and assert the leaderboard shows the extracted gamertags. Real clicks, real
  assertions, no `test.skip()`.

## Provisioning (first-time, Blake)

- GCP project (existing or new). Enable **Firestore (Native mode)** and
  **Cloud Storage**. Vertex AI is **not** needed.
- Create the bucket (e.g. `haloheads-uploads`) used with `pending/`,
  `analyzed/`, `failed/` prefixes.
- Cloud Run service account roles: **Firestore User**, **Storage Object Admin**
  (read + move). No AI roles.
- Deploy via the existing `Dockerfile`. Server image drops
  `google-cloud-vision`; keeps `flask`, `gunicorn`, `google-cloud-firestore`,
  `google-cloud-storage`, `Pillow`. The `anthropic` SDK belongs only to the
  analyzer's requirements, never the server image.
- Local analyzer prerequisites: `gcloud auth application-default login` and
  `ANTHROPIC_API_KEY` in the environment.

## Known limitations

- Map is often absent from the carnage report, so "best per map" is sparse
  unless uploaders fill the optional map field.
- One upload = one match (the carnage report shows only the just-finished game).
- The same gamertag spelled differently across games is treated as distinct
  (no fuzzy matching in v1).

## Prerequisite to confirm

- An `ANTHROPIC_API_KEY` is available for the local analyzer (this replaces the
  dropped Vertex path).
