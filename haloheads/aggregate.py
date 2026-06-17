import re

from .schema import kd

_TIME_RE = re.compile(r"^\d+:\d{2}$")


def _to_number(v):
    """Return (kind, value) where kind is 'time' (seconds) or 'num', else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return ("num", float(v))
    if isinstance(v, str):
        s = v.strip()
        if _TIME_RE.match(s):
            minutes, seconds = s.split(":")
            return ("time", int(minutes) * 60 + int(seconds))
        try:
            return ("num", float(s.replace("+", "")))
        except ValueError:
            return None
    return None


def _fmt_time(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _fmt_num(x):
    r = round(x, 2)
    return int(r) if r == int(r) else r


def tab_career(matches):
    """Career rollup of the extra (non-OVERVIEW) tabs.

    For each distinct tab name, group player rows by gamertag and average each
    numeric column across all games (M:SS times averaged in seconds and
    re-formatted). OVERVIEW is excluded — the leaderboard already covers it.
    """
    column_order = {}
    buckets = {}
    for m in matches:
        for tab in (m.get("tabs") or []):
            name = tab.get("name") or ""
            if name.upper() == "OVERVIEW":
                continue
            cols = column_order.setdefault(name, [])
            for c in (tab.get("columns") or []):
                if c not in cols:
                    cols.append(c)
            bucket = buckets.setdefault(name, {})
            for p in (tab.get("players") or []):
                g = p.get("gamertag")
                if not g:
                    continue
                entry = bucket.setdefault(
                    g, {"games": 0, "clan_tag": p.get("clan_tag"), "team": p.get("team"), "cols": {}}
                )
                entry["games"] += 1
                for col, val in (p.get("stats") or {}).items():
                    parsed = _to_number(val)
                    if parsed is not None:
                        entry["cols"].setdefault(col, []).append(parsed)

    result = {}
    for name, bucket in buckets.items():
        rows = []
        for g, entry in bucket.items():
            stats = {}
            for col, vals in entry["cols"].items():
                avg = sum(v for _, v in vals) / len(vals)
                stats[col] = _fmt_time(avg) if any(k == "time" for k, _ in vals) else _fmt_num(avg)
            rows.append({
                "gamertag": g, "games": entry["games"],
                "clan_tag": entry["clan_tag"], "team": entry["team"], "stats": stats,
            })
        rows.sort(key=lambda r: (-r["games"], r["gamertag"]))
        result[name] = {"columns": column_order[name], "rows": rows}
    return result


def leaderboard(rows):
    totals = {}
    for r in rows:
        g = r["gamertag"]
        if g not in totals:
            totals[g] = {
                "gamertag": g,
                "games": 0,
                "kills": 0,
                "deaths": 0,
                "assists": 0,
                "score": 0,
                "wins": 0,
            }
        t = totals[g]
        t["games"] += 1
        t["kills"] += r["kills"]
        t["deaths"] += r["deaths"]
        t["assists"] += r["assists"]
        t["score"] += r["score"]
        if r["result"] == "WON":
            t["wins"] += 1

    result = []
    for t in totals.values():
        entry = dict(t)
        entry["net_kd"] = kd(t["kills"], t["deaths"])
        entry["win_rate"] = round(t["wins"] / t["games"], 2)
        result.append(entry)

    result.sort(key=lambda e: (e["net_kd"], e["kills"]), reverse=True)
    return result


def mvps(matches, rows):
    rows_by_match = {}
    for r in rows:
        mid = r["match_id"]
        if mid not in rows_by_match:
            rows_by_match[mid] = []
        rows_by_match[mid].append(r)

    result = []
    for match in matches:
        mid = match["match_id"]
        match_rows = rows_by_match.get(mid, [])
        teams = {}
        for r in match_rows:
            team = r["team"]
            if team not in teams or r["score"] > teams[team]["score"]:
                teams[team] = r
        for team, r in teams.items():
            result.append({
                "match_id": mid,
                "team": team,
                "gamertag": r["gamertag"],
                "score": r["score"],
            })

    return result


def by_gametype(rows):
    grouped = {}
    for r in rows:
        g = r["gametype"]
        if g not in grouped:
            grouped[g] = []
        grouped[g].append(r)
    return {g: leaderboard(rs) for g, rs in grouped.items()}


def by_map(rows):
    grouped = {}
    for r in rows:
        m = r.get("map")
        if m is None:
            continue
        if m not in grouped:
            grouped[m] = []
        grouped[m].append(r)
    return {m: leaderboard(rs) for m, rs in grouped.items()}
