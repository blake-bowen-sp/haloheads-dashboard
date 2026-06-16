from .schema import CarnageReport, result_for, kd, row_hash


def build_docs(report, *, match_id, source_image, img_hash, uploaded_at, analyzed_at):
    match = {
        "match_id": match_id,
        "gametype": report.gametype.upper(),
        "map": report.map,
        "winning_team": report.winning_team,
        "source_image": source_image,
        "uploaded_at": uploaded_at,
        "analyzed_at": analyzed_at,
        "image_hash": img_hash,
    }

    players = []
    for p in report.players:
        players.append({
            "match_id": match_id,
            "gamertag": p.gamertag,
            "clan_tag": p.clan_tag,
            "team": p.team,
            "result": result_for(p.team, report.winning_team),
            "score": p.score,
            "kills": p.kills,
            "assists": p.assists,
            "deaths": p.deaths,
            "kd": kd(p.kills, p.deaths),
            "gametype": report.gametype.upper(),
            "map": report.map,
            "created_at": analyzed_at,
            "row_hash": row_hash(match_id, p.gamertag, p.score, p.kills, p.assists, p.deaths),
        })

    return match, players
