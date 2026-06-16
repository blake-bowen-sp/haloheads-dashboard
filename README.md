# Haloheads Stats

Haloheads is a stats-tracking system for a private Halo game group. Players upload photos of in-game post-game carnage reports (the end-of-match scoreboard) to a web app. On demand, **Claude Code reads the photos and extracts per-player stats** — no API key required — and writes them to a datastore. The dashboard then surfaces leaderboards, MVPs, game-type breakdowns, and per-player history, all keyed by gamertag.

## How it works

1. A player uploads a post-game photo at `/upload` — the file is stored to a bucket (GCS in prod, local filesystem in dev). The gamertags come from the photo, so there's nothing to type.
2. On demand, Aaron tells Claude Code to analyze. Claude Code stages the un-analyzed photos (`scripts/stage.py`), **reads each one with its own vision**, and ingests the extracted stats (`scripts/ingest.py`) into the store (Firestore in prod, SQLite in dev). No Anthropic API key is involved.
3. The Flask dashboard (`app.py`, deployed to Cloud Run) reads the store and serves the leaderboard and player pages.

Analysis is on-demand, not automatic. The server holds no Anthropic key and never calls Claude. (An optional fully-automated path using an API key also exists — see below.)

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
pytest -q                       # unit + integration + e2e (golden test skips without a key)
ANTHROPIC_API_KEY=sk-... pytest tests/test_extraction_golden.py -v   # real-Claude golden test
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
| `ANTHROPIC_API_KEY` | _(none)_ | optional — only the automated `scripts/analyze.py` path; the Claude Code stage/ingest path needs no key |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | automated `scripts/analyze.py` only |
| `HALOHEADS_FAKE_EXTRACT` | _(unset)_ | `scripts/analyze.py` (set to `1` to skip the API in dev) |

## Deploy (GCP, one-time provisioning by Blake)

1. Pick or create a GCP project; enable Firestore (Native mode) and Cloud Storage. Vertex AI is NOT used.
2. Create the bucket:
   ```
   gcloud storage buckets create gs://haloheads-uploads
   ```
3. Grant the Cloud Run service account two roles: **Firestore User**, **Storage Object Admin**.
4. Deploy:
   ```
   gcloud run deploy haloheads --source . \
     --set-env-vars STORAGE_BACKEND=gcs,GCS_BUCKET=haloheads-uploads,STORE_BACKEND=firestore,GCP_PROJECT=<project>
   ```

The server holds no Anthropic key — only the local analyzer calls Claude.

## Design docs

See `docs/superpowers/specs/` and `docs/superpowers/plans/`.
