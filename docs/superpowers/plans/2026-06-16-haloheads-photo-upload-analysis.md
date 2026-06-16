# Haloheads Photo Upload + On-Demand Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let anyone upload a photo of the in-game Halo post-game carnage report; a locally-run script extracts stats with Claude vision and updates a Firestore-backed dashboard.

**Architecture:** Three decoupled pieces sharing one GCP project. A thin Flask **collector** (Cloud Run) stores uploaded photos in object storage. A local **analyzer** CLI pulls un-analyzed photos, extracts stats via Claude vision (local `ANTHROPIC_API_KEY`, no Vertex), and writes them to the stats store. The **dashboard** (same Flask app) reads the store. Storage and store are behind adapters: filesystem + SQLite locally (so the whole pipeline self-tests with no cloud), GCS + Firestore in production.

**Tech Stack:** Python 3.12, Flask, Anthropic SDK (vision tool-use), google-cloud-storage, google-cloud-firestore, Pillow, pytest, pytest-playwright.

---

## Design rules (from user's CLAUDE.md)

- No `enum` → use `typing.Literal[...]` string-literal unions. Prefer dataclasses.
- No bare `Any`. Handle errors explicitly; never swallow. Keep it minimal, no premature abstraction beyond the adapters justified by testability.
- Don't add comments/docstrings/type annotations to code you didn't change.
- Real end-to-end Playwright test driving the actual upload UI. No `test.skip()` on the UI path.
- Semantic-delta test: changing the image must change stored stats (guard against a stubbed extractor).

## File structure

```
app.py                          # MODIFY  Flask collector + dashboard + JSON APIs
haloheads/
  __init__.py                   # CREATE  package marker
  schema.py                     # CREATE  dataclasses, validation, derived fields, hashing
  storage.py                    # CREATE  Storage adapter: LocalStorage | GcsStorage + get_storage()
  store.py                      # CREATE  Store adapter: SqliteStore | FirestoreStore + get_store()
  extraction.py                 # CREATE  Claude vision extraction + tool schema + get_extractor()
  aggregate.py                  # CREATE  pure ranking functions over player_stats rows
  docs.py                       # CREATE  build match/player Firestore-shaped dicts from a CarnageReport
scripts/
  analyze.py                    # CREATE  analyzer CLI
  make_icons.py                 # CREATE  generate PWA PNG icons with Pillow
templates/
  dashboard.html                # MODIFY  leaderboard + MVPs + per-gametype, keep matrix theme
  upload.html                   # MODIFY  PWA upload, iOS capture, preview, optional map, progress
static/
  style.css                     # MODIFY  styles for new sections + upload page
  manifest.webmanifest          # CREATE  PWA manifest
  sw.js                         # CREATE  minimal service worker
  icon-192.png / icon-512.png / apple-touch-icon.png  # CREATE via make_icons.py
tests/
  conftest.py                   # CREATE  fixtures: temp local storage+sqlite, app client, sample image path
  fixtures/carnage_blue.py      # CREATE  expected CarnageReport for testTeamResultData.jpeg (golden values)
  test_schema.py                # CREATE
  test_aggregate.py             # CREATE
  test_store_sqlite.py          # CREATE
  test_store_firestore.py       # CREATE  (mocked firestore client)
  test_analyzer.py              # CREATE  pipeline with fake extractor (dedup, move, dry-run)
  test_extraction_golden.py     # CREATE  real Claude, gated on ANTHROPIC_API_KEY
  test_semantic_delta.py        # CREATE  two images -> different leaderboards
  e2e/test_upload_dashboard.py  # CREATE  pytest-playwright real UI path
requirements.txt                # MODIFY  server deps (drop vision/Pillow)
requirements-analyzer.txt       # CREATE  analyzer deps
requirements-dev.txt            # CREATE  test deps
.env.example                    # CREATE  documented env vars
.gitignore                      # CREATE
Dockerfile                      # MODIFY  server image only
README.md                       # MODIFY  setup + run
```

## Configuration (env vars, with local defaults)

| Var | Default | Used by |
|---|---|---|
| `STORAGE_BACKEND` | `local` | all (`local`\|`gcs`) |
| `STORAGE_DIR` | `./.localdata/bucket` | LocalStorage |
| `GCS_BUCKET` | `haloheads-uploads` | GcsStorage |
| `STORE_BACKEND` | `sqlite` | all (`sqlite`\|`firestore`) |
| `SQLITE_PATH` | `./.localdata/stats.db` | SqliteStore |
| `GCP_PROJECT` | unset | FirestoreStore |
| `ANTHROPIC_API_KEY` | unset | analyzer real extract |
| `ANTHROPIC_MODEL` | (pin during Task 6) | analyzer |
| `HALOHEADS_FAKE_EXTRACT` | unset | tests/E2E force fake |

Prod collector (Cloud Run): `STORAGE_BACKEND=gcs`, `STORE_BACKEND=firestore`, `GCS_BUCKET`, `GCP_PROJECT`.
Prod analyzer (Aaron, local): same as collector + `ANTHROPIC_API_KEY` + ADC (`gcloud auth application-default login`).

## Golden values — `gameStatsImageFiles/testTeamResultData.jpeg`

Header: **BLUE TEAM WON**, gametype string contains **SLAYER** (full header "LEGENDARY SLAYER BR"). Columns: SCORE, KILLS, ASSISTS, DEATHS.

| gamertag | clan | team | score | kills | assists | deaths |
|---|---|---|---|---|---|---|
| Cyborg800 | 4039 | BLUE | 250 | 19 | 5 | 4 |
| X Jack X7282 | UNSC | BLUE | 225 | 16 | 6 | 5 |
| Lord Celtic XxX | BEASTMODE ON | BLUE | 205 | 11 | 11 | 6 |
| Cursorycash5200 | Seekers | BLUE | 80 | 4 | 5 | 11 |
| ELIMINADOR | DIEGO | RED | 195 | 14 | 1 | 10 |
| ScaredBOB | UNSC | RED | 100 | 6 | 1 | 9 |
| Archer 6820(1) | UNSC | RED | 25 | 2 | 1 | 16 |
| Archer 6820 | UNSC | RED | 15 | 1 | 1 | 16 |

These are the exact assertions for the golden and semantic-delta tests.

---

## Task 0: Repo init + scaffolding

**Files:** Create `.gitignore`, `haloheads/__init__.py`, `requirements-analyzer.txt`, `requirements-dev.txt`, `.env.example`.

- [ ] **Step 1:** `git init` (repo is not yet under git). Create `.gitignore` with: `.localdata/`, `__pycache__/`, `*.pyc`, `.env`, `.pytest_cache/`, `node_modules/`, `.DS_Store`, `*.db`.
- [ ] **Step 2:** Create `haloheads/__init__.py` (empty).
- [ ] **Step 3:** Create `requirements-analyzer.txt`: `anthropic==0.87.0`, `google-cloud-storage==2.11.0`, `google-cloud-firestore==2.14.0`, `Pillow==10.2.0`, `python-dotenv==1.0.1`.
- [ ] **Step 4:** Create `requirements-dev.txt`: `-r requirements-analyzer.txt`, `pytest==8.*`, `pytest-playwright==0.*`, `Flask==3.0.0`.
- [ ] **Step 5:** Create `.env.example` documenting the table above.
- [ ] **Step 6:** `pip install -r requirements-dev.txt` then `python -m playwright install chromium`.
- [ ] **Step 7:** Commit: `chore: repo init, deps, scaffolding`.

## Task 1: `schema.py` — types, validation, derived fields, hashing

**Files:** Create `haloheads/schema.py`, `tests/test_schema.py`.

Types & functions:
```python
from dataclasses import dataclass
from typing import Literal, Optional
import hashlib

Team = Literal["BLUE", "RED"]
Result = Literal["WON", "LOST"]

@dataclass
class PlayerRow:
    gamertag: str
    clan_tag: Optional[str]
    team: Team
    score: int
    kills: int
    assists: int
    deaths: int

@dataclass
class CarnageReport:
    winning_team: Team
    gametype: str
    map: Optional[str]
    players: list[PlayerRow]

def result_for(team: Team, winning_team: Team) -> Result:
    return "WON" if team == winning_team else "LOST"

def kd(kills: int, deaths: int) -> float:
    return float(kills) if deaths == 0 else round(kills / deaths, 2)

def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def row_hash(match_id: str, gamertag: str, score: int, kills: int, assists: int, deaths: int) -> str:
    raw = f"{match_id}|{gamertag}|{score}|{kills}|{assists}|{deaths}"
    return hashlib.sha256(raw.encode()).hexdigest()

def validate_report(data: dict) -> CarnageReport:
    # raises ValueError on: bad winning_team, empty players, non-int stats, bad team
```

- [ ] **Step 1:** Write `tests/test_schema.py`: valid dict → CarnageReport with 8 players; invalid winning_team → ValueError; empty players → ValueError; negative/str stat → ValueError; `result_for("RED","BLUE")=="LOST"`, `result_for("BLUE","BLUE")=="WON"`; `kd(19,4)==4.75`, `kd(5,0)==5.0`; `image_hash` deterministic; `row_hash` differs when any field differs.
- [ ] **Step 2:** Run `pytest tests/test_schema.py -v` → FAIL (module missing).
- [ ] **Step 3:** Implement `haloheads/schema.py`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `feat(schema): carnage report types, validation, hashing`.

## Task 2: `docs.py` — build store-shaped dicts from a report

**Files:** Create `haloheads/docs.py`, add to `tests/test_schema.py` (or `tests/test_docs.py`).

```python
from .schema import CarnageReport, result_for, kd, row_hash

def build_docs(report: CarnageReport, *, match_id: str, source_image: str, img_hash: str,
               uploaded_at: str, analyzed_at: str) -> tuple[dict, list[dict]]:
    match = {"match_id": match_id, "gametype": report.gametype.upper(), "map": report.map,
             "winning_team": report.winning_team, "source_image": source_image,
             "uploaded_at": uploaded_at, "analyzed_at": analyzed_at, "image_hash": img_hash}
    players = [{"match_id": match_id, "gamertag": p.gamertag, "clan_tag": p.clan_tag,
                "team": p.team, "result": result_for(p.team, report.winning_team),
                "score": p.score, "kills": p.kills, "assists": p.assists, "deaths": p.deaths,
                "kd": kd(p.kills, p.deaths), "gametype": report.gametype.upper(), "map": report.map,
                "created_at": analyzed_at,
                "row_hash": row_hash(match_id, p.gamertag, p.score, p.kills, p.assists, p.deaths)}
               for p in report.players]
    return match, players
```

- [ ] **Step 1:** Test: build_docs on the golden report → match.winning_team BLUE, 8 player dicts, ELIMINADOR result "LOST", Cyborg800 kd 4.75, every player has unique row_hash.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `feat(docs): map CarnageReport to store documents`.

## Task 3: `storage.py` — Local + GCS adapters

**Files:** Create `haloheads/storage.py`, `tests/conftest.py` (temp dir fixture), `tests/test_storage_local.py`.

Interface (Protocol) + factory:
```python
class Storage(Protocol):
    def save_upload(self, data: bytes, content_type: str, meta: dict) -> str: ...
    def list_pending(self) -> list[str]: ...
    def read(self, key: str) -> bytes: ...
    def move(self, key: str, dest_prefix: str) -> str: ...   # returns new key
    def meta(self, key: str) -> dict: ...

def get_storage() -> Storage:  # STORAGE_BACKEND: local|gcs
```
`LocalStorage(root)`: layout `root/pending/`, `root/analyzed/`, `root/failed/`; `save_upload` writes `pending/<uuid>.jpg` + `pending/<uuid>.json` (meta); `list_pending` returns `pending/<uuid>.jpg` keys sorted; `move` relocates both blob+sidecar.
`GcsStorage(bucket)`: same key semantics via `google.cloud.storage`; meta stored as object metadata; `move` = copy+delete.

- [ ] **Step 1:** Test (LocalStorage on tmp_path): save_upload → key under `pending/`, read round-trips bytes, meta round-trips; list_pending returns it; move(key,"analyzed/") → key under `analyzed/`, gone from pending; get_storage() honors `STORAGE_BACKEND=local`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement both adapters (GCS adapter not unit-tested live; keep it thin and obvious).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `feat(storage): local + gcs storage adapters`.

## Task 4: `store.py` — SQLite + Firestore adapters

**Files:** Create `haloheads/store.py`, `tests/test_store_sqlite.py`, `tests/test_store_firestore.py`.

```python
class Store(Protocol):
    def match_exists(self, image_hash: str) -> bool: ...
    def add_match(self, match: dict, players: list[dict]) -> None: ...
    def all_player_stats(self) -> list[dict]: ...
    def all_matches(self) -> list[dict]: ...

def get_store() -> Store:  # STORE_BACKEND: sqlite|firestore
```
`SqliteStore(path)`: creates tables `matches(match_id PK, gametype, map, winning_team, source_image, uploaded_at, analyzed_at, image_hash UNIQUE)` and `player_stats(...cols..., row_hash UNIQUE)`; `add_match` inserts in a transaction, `INSERT OR IGNORE` on row_hash; `match_exists` checks image_hash.
`FirestoreStore(project)`: collections `matches`, `player_stats`; `add_match` writes docs; `match_exists` queries `matches.where(image_hash==)`.

- [ ] **Step 1:** SQLite test: add golden match+players → all_player_stats() returns 8 rows; match_exists(img_hash) True; re-add same → still 8 (dedup); all_matches() returns 1.
- [ ] **Step 2:** Firestore test: monkeypatch `google.cloud.firestore.Client` with a fake; assert add_match calls `collection("matches").document().set(...)` and 8 `player_stats` writes; match_exists uses a where-query.
- [ ] **Step 3:** Run → FAIL.
- [ ] **Step 4:** Implement both.
- [ ] **Step 5:** Run → PASS.
- [ ] **Step 6:** Commit: `feat(store): sqlite + firestore stat stores`.

## Task 5: `aggregate.py` — ranking functions

**Files:** Create `haloheads/aggregate.py`, `tests/test_aggregate.py`.

```python
def leaderboard(rows: list[dict]) -> list[dict]   # per gamertag: games, kills, deaths, assists, score, wins, net_kd, win_rate; sorted by net_kd desc
def mvps(matches: list[dict], rows: list[dict]) -> list[dict]   # per match, per team: highest-score player
def by_gametype(rows: list[dict]) -> dict[str, list[dict]]      # gametype -> leaderboard
def by_map(rows: list[dict]) -> dict[str, list[dict]]           # map -> leaderboard (skip null map)
```

- [ ] **Step 1:** Test with the 8 golden rows (+ a duplicate gamertag across 2 synthetic matches): leaderboard top entry is the highest net K/D; Cyborg800 net_kd 4.75 with 1 game; gamertag appearing twice has games==2 and summed stats; mvps returns BLUE MVP Cyborg800 (250) and RED MVP ELIMINADOR (195); by_gametype has a "SLAYER" key; by_map skips null maps.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement (pure functions, no I/O).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `feat(aggregate): leaderboard, mvps, per-gametype/map`.

## Task 6: `extraction.py` — Claude vision

**Files:** Create `haloheads/extraction.py`, `tests/fixtures/carnage_blue.py`.

> **REQUIRED:** Before writing this file, load the **claude-api** skill to pin the current Claude model id, the vision message format (base64 image block), and tool-use for forced structured output. Use a current Sonnet-class model; set `ANTHROPIC_MODEL` default accordingly.

```python
TOOL = {"name": "record_carnage_report", "description": "...", "input_schema": {
  "type": "object", "required": ["winning_team","gametype","map","players"],
  "properties": {
    "winning_team": {"type":"string","enum":["BLUE","RED"]},
    "gametype": {"type":"string"},
    "map": {"type":["string","null"]},
    "players": {"type":"array","items":{"type":"object",
      "required":["gamertag","clan_tag","team","score","kills","assists","deaths"],
      "properties":{"gamertag":{"type":"string"},"clan_tag":{"type":["string","null"]},
        "team":{"type":"string","enum":["BLUE","RED"]},"score":{"type":"integer"},
        "kills":{"type":"integer"},"assists":{"type":"integer"},"deaths":{"type":"integer"}}}}}}}

PROMPT = ("Read this Halo post-game carnage report. Team is set by row color "
          "(blue rows = BLUE, red rows = RED). Keep the clan tag in [brackets] "
          "separate from the gamertag. Return integers for score/kills/assists/deaths. "
          "Use null for map if no map name is shown. Call record_carnage_report.")

def extract_carnage_report(data: bytes, *, client=None, model=None) -> CarnageReport:
    # downscale via Pillow to max 1568px, base64, messages.create with TOOL + tool_choice,
    # read tool_use input, validate_report(...)

def get_extractor():  # returns fake when HALOHEADS_FAKE_EXTRACT=1, else extract_carnage_report
```
`tests/fixtures/carnage_blue.py` exposes `CARNAGE_BLUE` (the golden CarnageReport) and `fake_extract(data)` that returns it.

- [ ] **Step 1:** Load claude-api skill; pin model id + vision/tool format.
- [ ] **Step 2:** Write `tests/fixtures/carnage_blue.py` with the golden values from the table.
- [ ] **Step 3:** Unit test (no network): monkeypatch a fake Anthropic client returning a `tool_use` block with the golden input → extract_carnage_report parses it to the golden report; malformed tool input → ValueError.
- [ ] **Step 4:** Run → FAIL, then implement, then PASS.
- [ ] **Step 5:** Commit: `feat(extraction): claude vision carnage-report extraction`.

## Task 7: `scripts/analyze.py` — analyzer CLI

**Files:** Create `scripts/analyze.py`, `tests/test_analyzer.py`.

Flow: parse args (`--dry-run`,`--all`,`--image PATH`,`--limit N`); `storage=get_storage()`, `store=get_store()`, `extract=get_extractor()`; for each pending key (or single `--image`): read bytes → `h=image_hash` → if `store.match_exists(h)` and not `--all`: move→analyzed, continue → `report=extract(data)` (on error move→failed, log, continue) → `build_docs(...)` → if dry-run print JSON else `store.add_match` + move→analyzed; print summary counts.

- [ ] **Step 1:** Test (LocalStorage + SqliteStore on tmp, `HALOHEADS_FAKE_EXTRACT=1`): save the sample image bytes as a pending upload; run analyzer main(); assert store has 1 match + 8 players, image moved to `analyzed/`; run again → no duplicates, nothing in pending; `--dry-run` writes nothing.
- [ ] **Step 2:** Run → FAIL, implement, → PASS.
- [ ] **Step 3:** Commit: `feat(analyzer): on-demand analyze CLI with dedup + dry-run`.

## Task 8: Flask collector + dashboard APIs

**Files:** Modify `app.py`.

Routes: `GET /` (dashboard), `GET /upload` (form), `POST /upload` (multipart `image` + optional `map` → `get_storage().save_upload(...)` → JSON `{ok, key}`), `GET /api/leaderboard`, `GET /api/mvps`, `GET /api/gametypes`, `GET /api/player/<tag>`, `GET /health`. Remove the Vision/regex/Firestore-write code, `/ingest`, `/generate-upload-url`, and `/api/playerstats`. APIs read via `get_store()` + `aggregate`.

- [ ] **Step 1:** Test (Flask test client, Local+SQLite tmp): `POST /upload` with the sample image → 200, key under pending, file present; pre-seed store with golden docs → `GET /api/leaderboard` returns Cyborg800 first; `/health` ok.
- [ ] **Step 2:** Run → FAIL, implement, → PASS.
- [ ] **Step 3:** Commit: `feat(app): collector upload + dashboard JSON APIs`.

## Task 9: Frontend — PWA upload + dashboard

**Files:** Modify `templates/upload.html`, `templates/dashboard.html`, `static/style.css`; create `static/manifest.webmanifest`, `static/sw.js`, `scripts/make_icons.py` + icons.

- `upload.html`: `<input type="file" accept="image/*" id="file">` (NO `capture` attr → iOS shows Take Photo / Photo Library / Choose File), optional `<input type="text" id="map" placeholder="map (optional)">`, thumbnail preview, submit via `fetch('/upload',{method:'POST',body:FormData})`, progress + success/error text. `<head>`: `<link rel="manifest" href="/static/manifest.webmanifest">`, `<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">`, `<meta name="apple-mobile-web-app-capable" content="yes">`, register `/static/sw.js`.
- `dashboard.html`: fetch `/api/leaderboard`, `/api/mvps`, `/api/gametypes`; render leaderboard table (gamertag, games, K, D, A, net K/D, win%), an MVPs section, and per-gametype tables. Keep matrix-rain.
- `manifest.webmanifest`: name, theme `#00ff9c`, bg `#050505`, display standalone, icons 192/512.
- `sw.js`: cache-first for static shell.
- `make_icons.py`: render a simple HALO-green "H" PNG at 192/512 + 180 apple-touch via Pillow.

- [ ] **Step 1:** `python scripts/make_icons.py` to generate icons.
- [ ] **Step 2:** Implement templates/manifest/sw/css.
- [ ] **Step 3:** Manual smoke: `flask --app app run` → load `/upload` and `/` locally.
- [ ] **Step 4:** Commit: `feat(ui): PWA upload with iOS capture + dashboard views`.

## Task 10: Semantic-delta test

**Files:** Create `tests/test_semantic_delta.py`, add a second fixture `tests/fixtures/carnage_red.py` (a hand-made different report: RED wins, different gamertags/stats).

- [ ] **Step 1:** Pipeline with fake extractor mapping image-A→blue fixture, image-B→red fixture (by filename); analyze both; assert leaderboards differ and each report's gamertags appear only from its own image. Guards that stored stats are a function of the image, not a constant.
- [ ] **Step 2:** Run → FAIL, implement mapping hook, → PASS.
- [ ] **Step 3:** Commit: `test: semantic-delta guard on extraction`.

## Task 11: Golden integration test (real Claude)

**Files:** Create `tests/test_extraction_golden.py`.

- [ ] **Step 1:** `@pytest.mark.skipif(no ANTHROPIC_API_KEY)`; call `extract_carnage_report(open('gameStatsImageFiles/testTeamResultData.jpeg','rb').read())`; assert winning_team BLUE, 8 players, and the exact per-player score/kills/assists/deaths from the golden table; gametype contains "SLAYER".
- [ ] **Step 2:** If a key is available, run it for real and confirm PASS (this is the only test that validates Claude actually reads the board). Otherwise document that it must be run with a key before release.
- [ ] **Step 3:** Commit: `test: golden real-Claude extraction on sample board`.

## Task 12: E2E Playwright (real UI path)

**Files:** Create `tests/e2e/test_upload_dashboard.py`.

- [ ] **Step 1:** Fixture starts Flask (Local storage + SQLite on a temp dir, `HALOHEADS_FAKE_EXTRACT=1`) on a port. Test: Playwright opens `/upload`, sets the file input to `testTeamResultData.jpeg`, clicks submit, asserts success text; then runs `analyze.main()` against the same temp backends; then navigates to `/`, asserts the leaderboard table renders rows containing `Cyborg800` and `ELIMINADOR`. Real clicks, real assertions, no skip.
- [ ] **Step 2:** Run `pytest tests/e2e -v` → PASS.
- [ ] **Step 3:** Commit: `test(e2e): real upload→analyze→dashboard flow`.

## Task 13: Deploy config + docs

**Files:** Modify `requirements.txt` (server: `flask`, `gunicorn`, `google-cloud-firestore`, `google-cloud-storage` — drop vision + Pillow), `Dockerfile` (server only; no anthropic), `README.md`.

- [ ] **Step 1:** Update `requirements.txt` + `Dockerfile`; keep Cloud Run `:8080` entrypoint.
- [ ] **Step 2:** README: local dev (`pip install -r requirements-dev.txt`, run flask, run analyzer), prod env vars, the GCP provisioning checklist (enable Firestore Native + Storage, create bucket, Cloud Run SA roles Firestore User + Storage Object Admin), and analyzer prerequisites (ADC + `ANTHROPIC_API_KEY`).
- [ ] **Step 3:** Run full suite `pytest -v` (golden test skips without key) → green; lint.
- [ ] **Step 4:** Commit: `chore: server deploy config + docs`.

---

## Self-review

**Spec coverage:** collector (T8/T9), analyzer (T7), dashboard (T8/T9), Claude-on-key-no-Vertex (T6), carnage-report schema/golden values (T1/T6/T11), Firestore + GCS prod / SQLite + FS local (T3/T4), dedup (T4/T7), iOS capture + PWA (T9), leaderboard/MVP/gametype/map rankings (T5), semantic-delta + golden + E2E tests (T10/T11/T12), provisioning + deploy docs (T13). All spec sections map to a task.

**Placeholder scan:** model id is the one deferred value, explicitly pinned in T6 via the claude-api skill (not left vague). No TBDs elsewhere.

**Type consistency:** `Team`/`Result` literals, `PlayerRow`/`CarnageReport`, `Storage`/`Store` protocols, `get_storage`/`get_store`/`get_extractor`, `build_docs`, `image_hash`/`row_hash`, `leaderboard`/`mvps`/`by_gametype`/`by_map` are used consistently across tasks.
