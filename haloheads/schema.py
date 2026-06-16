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
