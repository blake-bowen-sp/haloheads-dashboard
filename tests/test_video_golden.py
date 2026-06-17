"""Real-Gemini golden tests for video multi-tab extraction.

Gated on GEMINI_API_KEY (skips without it), like the Claude golden test. This is
the canonical "does Gemini actually read the video" check, plus a semantic-delta
guard (different video -> different stats) per the testing rules.
"""
import os
from pathlib import Path

import pytest

from haloheads.gemini import NotAScoreboard, extract_tabs_from_video
from haloheads.schema import canonical_report

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY"
)

FIX = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIX / name).read_bytes()


def _by_tag(report):
    return {p.gamertag.replace(" ", "").lower(): p for p in report.players}


def test_real_gemini_reads_multiple_tabs():
    multi = extract_tabs_from_video(_read("multitab_sample.mp4"), mime_type="video/mp4")

    names = [t.name.upper() for t in multi.tabs]
    assert any("OVERVIEW" in n for n in names), names
    assert any("DETAIL" in n or "STATS" in n for n in names), names
    assert multi.winning_team and multi.winning_team.upper() == "BLUE"

    report = canonical_report(multi)
    tags = _by_tag(report)
    assert "spartan117" in tags, list(tags)
    sp = tags["spartan117"]
    assert (sp.score, sp.kills, sp.deaths) == (300, 25, 6)
    assert tags["noblesix"].kills == 22

    detailed = next(t for t in multi.tabs if "OVERVIEW" not in t.name.upper())
    assert any("LIFE" in c.upper() for c in detailed.columns), detailed.columns


def test_real_gemini_semantic_delta():
    one = canonical_report(extract_tabs_from_video(_read("multitab_sample.mp4"), mime_type="video/mp4"))
    two = canonical_report(extract_tabs_from_video(_read("multitab_sample_2.mp4"), mime_type="video/mp4"))

    sp1 = _by_tag(one)["spartan117"]
    sp2 = _by_tag(two)["spartan117"]
    assert (sp1.kills, sp1.deaths) != (sp2.kills, sp2.deaths)
    assert one.winning_team.upper() == "BLUE"
    assert two.winning_team.upper() == "RED"


def test_real_gemini_rejects_non_scoreboard():
    with pytest.raises(NotAScoreboard):
        extract_tabs_from_video(_read("notscoreboard_sample.mp4"), mime_type="video/mp4")
