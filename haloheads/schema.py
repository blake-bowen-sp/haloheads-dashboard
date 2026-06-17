from dataclasses import dataclass
from typing import Optional
import hashlib

Team = str
Result = str


@dataclass
class PlayerRow:
    gamertag: str
    clan_tag: Optional[str]
    team: Optional[str]
    score: int
    kills: int
    assists: int
    deaths: int


@dataclass
class CarnageReport:
    winning_team: Optional[str]
    gametype: str
    map: Optional[str]
    players: list[PlayerRow]


@dataclass
class TabPlayer:
    gamertag: str
    clan_tag: Optional[str]
    team: Optional[str]
    stats: dict


@dataclass
class Tab:
    name: str
    columns: list[str]
    players: list[TabPlayer]


@dataclass
class MultiTabReport:
    winning_team: Optional[str]
    gametype: str
    map: Optional[str]
    tabs: list[Tab]


SKAD = ("SCORE", "KILLS", "ASSISTS", "DEATHS")


def result_for(team, winning_team):
    if not winning_team or not team:
        return ""
    return "WON" if team == winning_team else "LOST"


def kd(kills, deaths):
    return float(kills) if deaths == 0 else round(kills / deaths, 2)


def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def row_hash(match_id, gamertag, score, kills, assists, deaths) -> str:
    raw = f"{match_id}|{gamertag}|{score}|{kills}|{assists}|{deaths}"
    return hashlib.sha256(raw.encode()).hexdigest()


def game_hash(winning_team, gametype, players) -> str:
    rows = sorted(f"{p.gamertag}|{p.score}|{p.kills}|{p.assists}|{p.deaths}" for p in players)
    raw = f"{winning_team or ''}|{(gametype or '').upper()}|" + "||".join(rows)
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_report(data: dict) -> CarnageReport:
    players_raw = data.get("players") or []
    if not players_raw:
        raise ValueError("players list must not be empty")

    players = []
    for p in players_raw:
        gamertag = p.get("gamertag")
        if not gamertag:
            raise ValueError("player missing gamertag")

        for field in ("score", "kills", "assists", "deaths"):
            val = p.get(field)
            if val is None:
                val = 0
            elif isinstance(val, bool) or not isinstance(val, int):
                raise ValueError(f"player {field} must be int, got {type(val).__name__}")
            elif val < 0:
                raise ValueError(f"player {field} must be >= 0, got {val}")
            p = {**p, field: val}

        players.append(PlayerRow(
            gamertag=gamertag,
            clan_tag=p.get("clan_tag"),
            team=p.get("team"),
            score=p["score"],
            kills=p["kills"],
            assists=p["assists"],
            deaths=p["deaths"],
        ))

    return CarnageReport(
        winning_team=data.get("winning_team"),
        gametype=data.get("gametype") or "",
        map=data.get("map"),
        players=players,
    )


def _coerce_stat(v):
    if v is None or isinstance(v, (int, float, str)):
        return v
    return str(v)


def validate_multitab(data: dict) -> MultiTabReport:
    tabs_raw = data.get("tabs") or []
    if not tabs_raw:
        raise ValueError("tabs list must not be empty")

    tabs = []
    for t in tabs_raw:
        players_raw = t.get("players") or []
        if not players_raw:
            raise ValueError("tab players list must not be empty")

        players = []
        for p in players_raw:
            gamertag = p.get("gamertag")
            if not gamertag:
                raise ValueError("tab player missing gamertag")
            stats = {str(k): _coerce_stat(v) for k, v in (p.get("stats") or {}).items()}
            players.append(TabPlayer(
                gamertag=gamertag,
                clan_tag=p.get("clan_tag"),
                team=p.get("team"),
                stats=stats,
            ))

        columns = [str(c) for c in (t.get("columns") or [])]
        if not columns:
            for pl in players:
                for k in pl.stats:
                    if k not in columns:
                        columns.append(k)

        tabs.append(Tab(name=str(t.get("name") or ""), columns=columns, players=players))

    return MultiTabReport(
        winning_team=data.get("winning_team"),
        gametype=data.get("gametype") or "",
        map=data.get("map"),
        tabs=tabs,
    )


def _to_int(v) -> int:
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))
    if isinstance(v, str):
        try:
            return int(round(float(v.strip().replace("+", ""))))
        except ValueError:
            return 0
    return 0


def _is_skad_tab(tab: Tab) -> bool:
    cols = {c.upper() for c in tab.columns}
    if all(k in cols for k in SKAD):
        return True
    keys = set()
    for p in tab.players:
        keys |= {k.upper() for k in p.stats}
    return all(k in keys for k in SKAD)


def canonical_report(multi: MultiTabReport) -> CarnageReport:
    """The OVERVIEW/score tab mapped onto the existing CarnageReport shape.

    Anchors a video (or image) to the same scoreboard data that powers the
    leaderboard, MVPs, and dedup. Extra tabs are carried separately. If no tab
    exposes SCORE/KILLS/ASSISTS/DEATHS, players is empty (handled as
    no_readable_stats upstream).
    """
    tab = next((t for t in multi.tabs if t.name.upper() == "OVERVIEW" and _is_skad_tab(t)), None)
    if tab is None:
        tab = next((t for t in multi.tabs if _is_skad_tab(t)), None)

    players = []
    if tab is not None:
        for p in tab.players:
            up = {k.upper(): v for k, v in p.stats.items()}
            players.append(PlayerRow(
                gamertag=p.gamertag,
                clan_tag=p.clan_tag,
                team=p.team,
                score=_to_int(up.get("SCORE", 0)),
                kills=_to_int(up.get("KILLS", 0)),
                assists=_to_int(up.get("ASSISTS", 0)),
                deaths=_to_int(up.get("DEATHS", 0)),
            ))

    return CarnageReport(
        winning_team=multi.winning_team,
        gametype=multi.gametype or "",
        map=multi.map,
        players=players,
    )


def overview_tab(report: CarnageReport) -> Tab:
    """A single OVERVIEW Tab synthesized from a CarnageReport (image uploads)."""
    return Tab(
        name="OVERVIEW",
        columns=list(SKAD),
        players=[TabPlayer(
            gamertag=p.gamertag,
            clan_tag=p.clan_tag,
            team=p.team,
            stats={"SCORE": p.score, "KILLS": p.kills, "ASSISTS": p.assists, "DEATHS": p.deaths},
        ) for p in report.players],
    )


def tabs_to_dicts(tabs: list[Tab]) -> list[dict]:
    return [
        {
            "name": t.name,
            "columns": list(t.columns),
            "players": [
                {"gamertag": p.gamertag, "clan_tag": p.clan_tag, "team": p.team, "stats": dict(p.stats)}
                for p in t.players
            ],
        }
        for t in tabs
    ]
