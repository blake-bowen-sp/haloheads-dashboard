from .schema import kd


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
