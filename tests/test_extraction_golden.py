import os

import pytest

from haloheads.extraction import extract_carnage_report

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires ANTHROPIC_API_KEY (real Claude call)",
)


def test_golden_blue_board(sample_image_bytes):
    report = extract_carnage_report(sample_image_bytes)
    assert report.winning_team == "BLUE"
    assert "SLAYER" in report.gametype.upper()
    by_tag = {p.gamertag: p for p in report.players}
    assert len(report.players) == 8
    expected = {
        "Cyborg800": (250, 19, 5, 4),
        "X Jack X7282": (225, 16, 6, 5),
        "Lord Celtic XxX": (205, 11, 11, 6),
        "Cursorycash5200": (80, 4, 5, 11),
        "ELIMINADOR": (195, 14, 1, 10),
        "ScaredBOB": (100, 6, 1, 9),
        "Archer 6820(1)": (25, 2, 1, 16),
        "Archer 6820": (15, 1, 1, 16),
    }
    for tag, (score, kills, assists, deaths) in expected.items():
        assert tag in by_tag, f"missing {tag}; got {list(by_tag)}"
        p = by_tag[tag]
        assert (p.score, p.kills, p.assists, p.deaths) == (score, kills, assists, deaths), tag
