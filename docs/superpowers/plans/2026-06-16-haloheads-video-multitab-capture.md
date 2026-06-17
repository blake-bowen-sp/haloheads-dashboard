# Plan — Video Multi-Tab Capture & Extraction

Spec: `docs/superpowers/specs/2026-06-16-haloheads-video-multitab-capture-design.md`.
TDD throughout: write/extend the test, watch it fail, implement, watch it pass.
Each phase ends green before the next begins.

## Phase 1 — Schema (`haloheads/schema.py`)
- [ ] Tests (`tests/test_schema.py`): `validate_multitab` happy/empty/not-scoreboard;
      `canonical_report` finds the SKAD/OVERVIEW tab, merges players by gamertag, and
      yields the right `CarnageReport`; `overview_tab(report)` round-trips.
- [ ] Add `TabPlayer`, `Tab`, `MultiTabReport`; `validate_multitab`, `canonical_report`,
      `overview_tab`, `tabs_to_dicts`. No change to existing `CarnageReport` types.

## Phase 2 — Gemini video (`haloheads/gemini.py`)
- [ ] Tests (`tests/test_gemini.py`): mock the File-API upload + `generateContent`;
      assert request carries `file_uri`, `videoMetadata.fps=5`, `mediaResolution`,
      and that the parsed result is a `MultiTabReport`; not-a-scoreboard raises.
- [ ] `extract_tabs_from_video`; `get_report_extractor()` fake on `HALOHEADS_FAKE_GEMINI=1`.
      Leave `extract_with_gemini` untouched.

## Phase 3 — Persistence (`storage.py`, `store.py`, `docs.py`)
- [ ] storage tests: save/list/move a `.mp4`; image/jpeg still `.jpg`.
- [ ] store tests: `tabs` JSON round-trips; `get_match`, `recent_matches`; update
      `test_match_keys` to include `tabs`.
- [ ] Extension-by-content-type; `tabs TEXT` migration + writes; new query methods;
      `build_docs(tabs=None)`.

## Phase 4 — App (`app.py`)
- [ ] Extend `tests/test_upload_analyze.py`: a fake video upload → `analyzed`, tabs
      stored, `.mp4` lands in `analyzed/`. Existing image tests stay green.
- [ ] `/upload` mimetype branch; inline-on `HALOHEADS_FAKE_GEMINI`; `MAX_CONTENT_LENGTH`
      64 MB; `GET /api/matches`, `GET /api/match/<id>`.

## Phase 5 — Frontend (`templates/dashboard.html`)
- [ ] `accept="image/*,video/*"`; Matches section + generic per-tab table renderer.

## Phase 6 — Test video fixture
- [ ] `tests/fixtures/make_test_video.py` (OpenCV/ffmpeg) → commit
      `tests/fixtures/multitab_sample.mp4` (OVERVIEW + DETAILED, known truth) and a
      `notscoreboard.mp4`.

## Phase 7 — Golden + E2E + suite
- [ ] `tests/test_video_golden.py` (real Gemini, gated on `GEMINI_API_KEY`): ≥2 tabs,
      exact values, merge; semantic-delta vs a second clip.
- [ ] `tests/e2e/test_video_upload.py` (`HALOHEADS_FAKE_GEMINI=1`): Upload button →
      `#up-input` `.mp4` → match + tab pages render. Real clicks, no skips.
- [ ] `pytest -q` green; `ruff check` clean.

## Phase 8 — Docs + Deploy
- [ ] README + `.env.example`: document Gemini inline path + video/tabs +
      `HALOHEADS_FAKE_GEMINI`.
- [ ] Obtain `GEMINI_API_KEY` (from existing Cloud Run service if set) to run the
      golden test for real.
- [ ] `gcloud run deploy haloheads --source .` (project `haloheads-dashboard`) with
      `GEMINI_API_KEY` set; smoke-test the live URL.

## Guardrails
- Don't break the Claude analyzer / stage-ingest paths (image-only, untouched).
- Keep every existing test green except the deliberate `test_match_keys` `+tabs` edit.
- No secrets printed or committed.
