# Haloheads Stats

Haloheads is a stats-tracking system for a private Halo game group. Players upload screenshots of in-game post-game carnage reports (the end-of-match scoreboard) to a web app. A separate local analyzer uses Claude vision to extract per-player stats from each image and write them to a datastore. The dashboard then surfaces leaderboards, MVPs, game-type breakdowns, and per-player history, all keyed by gamertag.

## How it works

1. A player uploads a post-game screenshot at `/upload` — the file is stored to a bucket (GCS in prod, local filesystem in dev).
2. On demand, Aaron (or an agent) runs `scripts/analyze.py` locally. It pulls un-analyzed photos from the bucket, sends each to Claude for stat extraction, and writes results to the store (Firestore in prod, SQLite in dev).
3. The Flask dashboard (`app.py`, deployed to Cloud Run) reads the store and serves leaderboard and player pages.

Analysis is on-demand, not automatic. The server holds no Anthropic key and never calls Claude.

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

## Running the analyzer for real

Against prod data (reads GCS bucket, writes Firestore):

```
gcloud auth application-default login        # GCP creds (read bucket, write Firestore)
export ANTHROPIC_API_KEY=sk-ant-...          # required for Claude
export STORAGE_BACKEND=gcs GCS_BUCKET=haloheads-uploads
export STORE_BACKEND=firestore GCP_PROJECT=<your-project>
python3 scripts/analyze.py                   # analyze all pending uploads
python3 scripts/analyze.py --dry-run         # preview extractions, write nothing
python3 scripts/analyze.py --image shot.jpg  # one local file
```

Other flags: `--all` (re-analyze already-processed images), `--limit N` (cap the number processed).

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
| `ANTHROPIC_API_KEY` | _(none)_ | analyzer only |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | analyzer only |
| `HALOHEADS_FAKE_EXTRACT` | _(unset)_ | analyzer (set to `1` to skip Claude in dev) |

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
