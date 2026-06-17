# Haloheads Stats

Haloheads is a stats-tracking system for a private Halo game group. Players upload photos of in-game post-game carnage reports (the end-of-match scoreboard) to a web app. On demand, **Claude Code reads the photos and extracts per-player stats** — no API key required — and writes them to a datastore. The dashboard then surfaces leaderboards, MVPs, game-type breakdowns, and per-player history, all keyed by gamertag.

## How it works

1. A player uploads a post-game photo at `/upload` — the file is stored to a bucket (GCS in prod, local filesystem in dev). The gamertags come from the photo, so there's nothing to type.
2. On demand, Aaron tells Claude Code to analyze. Claude Code stages the un-analyzed photos (`scripts/stage.py`), **reads each one with its own vision**, and ingests the extracted stats (`scripts/ingest.py`) into the store (Firestore in prod, SQLite in dev). No Anthropic API key is involved.
3. The Flask dashboard (`app.py`, deployed to Cloud Run) reads the store and serves the leaderboard and player pages.

Analysis is on-demand, not automatic. The server holds no Anthropic key and never calls Claude. (An optional fully-automated path using an API key also exists — see below.)

## Inline Gemini analysis + video tab capture (deployed path)

When `GEMINI_API_KEY` is set, the web app analyzes each upload **inline** at
`POST /upload` with Gemini (`gemini-3.5-flash`, override via `GEMINI_MODEL`) — no
separate analyzer step. The Upload button accepts **images or video**
(`accept="image/*,video/*"`; on iOS this offers *Take Photo/Video / Library /
Files*).

Halo's post-game carnage report is a multi-tab carousel (OVERVIEW, DETAILED STATS,
MEDALS…). Record a ~2-second clip flipping through the tabs and upload it: Gemini
reads **every tab** into a generic `{name, columns, players:[{gamertag, stats}]}`
structure (via the Files API, sampled at 5 fps, high media resolution). **One
video = one match = N tabs.** The OVERVIEW tab feeds the existing leaderboard /
MVPs / dedup unchanged; the extra tabs power two new dashboard areas:

- **Career — By Tab** (`GET /api/tab-career`): each extra tab's stats averaged per
  player across all games (times like `M:SS` averaged in seconds).
- **Matches** (`GET /api/matches`, `GET /api/match/<id>`): tap a game to flip
  through its tabs as pages mirroring the in-game report.

A single photo is just the one-tab case (its OVERVIEW). The Gemini path uses only
`requests` (already a server dependency); it never imports the Anthropic SDK.

Set `HALOHEADS_FAKE_GEMINI=1` to short-circuit the inline path to a deterministic
fake multi-tab report (used by the E2E test; no key needed). Keep clips short —
Cloud Run caps request bodies at ~32 MB.

## Local development

No cloud account or API key needed — runs on local filesystem and SQLite by default.

```
pip install -r requirements-dev.txt
python3 -m playwright install chromium   # for the e2e test

# run the app (filesystem + sqlite defaults):
python3 app.py        # serves http://localhost:8080

# upload a photo at /upload, then analyze with the fake extractor:
HALOHEADS_FAKE_EXTRACT=1 python3 scripts/analyze.py
```

## Analyzing uploads with Claude Code (primary path — no API key)

When you want the stats updated, tell Claude Code to analyze. It runs:

```
# 1. Stage un-analyzed photos locally and print a manifest (key -> local path):
python3 scripts/stage.py

# 2. Claude Code reads each staged image and writes its readings to a JSON file
#    mapping the image key -> a carnage-report object:
#    { "pending/<id>.jpg": { "winning_team": "BLUE", "gametype": "...", "map": null,
#                            "players": [ { "gamertag", "clan_tag", "team",
#                                           "score", "kills", "assists", "deaths" }, ... ] } }

# 3. Ingest those readings into the store (validates, dedups, moves photos to analyzed/):
python3 scripts/ingest.py --reports reports.json
```

For prod data, point at the cloud backends first:

```
gcloud auth application-default login   # GCP creds (read bucket, write Firestore)
export STORAGE_BACKEND=gcs GCS_BUCKET=haloheads-uploads
export STORE_BACKEND=firestore GCP_PROJECT=<your-project>
python3 scripts/stage.py                 # downloads pending photos for Claude to read
# ...Claude reads them, you ingest as above
```

`stage.py` flags: `--all` (re-stage already-analyzed), `--limit N`, `--stage-dir DIR`.

## Optional: fully-automated analyzer (needs an API key)

If you'd rather have analysis run hands-off (e.g. on a schedule) instead of through Claude Code, `scripts/analyze.py` calls the Anthropic API directly:

```
export ANTHROPIC_API_KEY=sk-ant-...          # only this path needs a key
export STORAGE_BACKEND=gcs GCS_BUCKET=haloheads-uploads
export STORE_BACKEND=firestore GCP_PROJECT=<your-project>
python3 scripts/analyze.py                    # analyze all pending uploads
python3 scripts/analyze.py --dry-run          # preview, write nothing
python3 scripts/analyze.py --image shot.jpg   # one local file
```

In dev you can exercise this path without a key using `HALOHEADS_FAKE_EXTRACT=1 python3 scripts/analyze.py`.

## Tests

```
pytest -q                       # unit + integration + e2e (golden tests skip without a key)
ANTHROPIC_API_KEY=sk-... pytest tests/test_extraction_golden.py -v   # real-Claude golden test
GEMINI_API_KEY=AIza... pytest tests/test_video_golden.py -v          # real-Gemini video tab extraction

# regenerate the synthetic multi-tab test videos (committed under tests/fixtures/):
python3 tests/fixtures/make_test_video.py
```

## Env vars

| Variable | Default | Used by |
|---|---|---|
| `STORAGE_BACKEND` | `local` | collector, analyzer |
| `STORAGE_DIR` | `./.localdata/bucket` | collector, analyzer (local storage only) |
| `GCS_BUCKET` | _(none)_ | collector, analyzer (gcs storage only) |
| `STORE_BACKEND` | `sqlite` | collector, analyzer, dashboard |
| `SQLITE_PATH` | `./.localdata/stats.db` | collector, analyzer, dashboard (sqlite only) |
| `GCP_PROJECT` | _(none)_ | collector, analyzer, dashboard (firestore only) |
| `GEMINI_API_KEY` | _(none)_ | enables inline analysis in the web app (images + tab videos); the deployed path |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Gemini model for inline analysis (images + video) |
| `HALOHEADS_FAKE_GEMINI` | _(unset)_ | set to `1` to fake the inline multi-tab path (E2E/tests, no key) |
| `ANTHROPIC_API_KEY` | _(none)_ | optional — only the automated `scripts/analyze.py` path; the Claude Code stage/ingest path needs no key |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | automated `scripts/analyze.py` only |
| `HALOHEADS_FAKE_EXTRACT` | _(unset)_ | `scripts/analyze.py` (set to `1` to skip the API in dev) |

## Deploy (GCP, one-time provisioning by Blake)

1. Pick or create a GCP project; enable Firestore (Native mode) and Cloud Storage. Vertex AI is NOT used.
2. Create the bucket:
   ```
   gcloud storage buckets create gs://haloheads-dashboard-uploads
   ```
3. Grant the Cloud Run service account two roles: **Firestore User**, **Storage Object Admin**.
4. Store the Gemini key in Secret Manager (enables inline image + video analysis):
   ```
   printf '%s' "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=- --project haloheads-dashboard
   ```
5. Deploy (the live service is `haloheads-dashboard` in `us-central1`; a source deploy
   preserves existing env vars + the `gemini-api-key` secret):
   ```
   gcloud run deploy haloheads-dashboard --source . --region us-central1 --project haloheads-dashboard
   ```
   First-time only, set the config:
   ```
   gcloud run deploy haloheads-dashboard --source . --region us-central1 \
     --set-env-vars STORAGE_BACKEND=gcs,GCS_BUCKET=haloheads-dashboard-uploads,STORE_BACKEND=firestore,GCP_PROJECT=haloheads-dashboard \
     --update-secrets GEMINI_API_KEY=gemini-api-key:latest
   ```

The server calls **Gemini** for inline analysis (key from Secret Manager); it holds no
Anthropic key — only the optional local `scripts/analyze.py` analyzer calls Claude.

## Design docs

See `docs/superpowers/specs/` and `docs/superpowers/plans/`.
