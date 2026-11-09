"""Data sources. Every fetcher returns the common normalized schema (see README)
or raises, so the caller can fall back to the next source.

All endpoints are unofficial and unverified until scripts/verify_sources.py has
run on GitHub Actions. Parsers are defensive: missing fields become None.
"""
import re, datetime as dt, os
from common import *

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/" + LEAGUE_ESPN
EMPTY_STATS = dict(possession_pct=None, shots=None, shots_on_target=None, xg=None, passes=None,
                   pass_accuracy_pct=None, long_balls=None, crosses=None, crosses_completed=None,
                   corners=None, attack_side=dict(left_pct=None, center_pct=None, right_pct=None),
                   final_third_entries=None, box_touches=None, tackles=None, interceptions=None,
                   fouls=None, saves=None, blocked_shots=None, clearances=None)


def norm_name(s):
    s = (s or "").lower()
    s = re.sub(r"\b(fc|cf|sc|the)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def same_team(a, b):
    a, b = norm_name(a), norm_name(b)
    return bool(a and b and (a == b or a in b or b in a))


# ---------------------------------------------------------------- ESPN
ESPN_STAT_MAP = {
    "possessionPct": "possession_pct", "totalShots": "shots", "shotsOnTarget": "shots_on_target",
    "totalPasses": "passes", "passPct": "pass_accuracy_pct", "totalLongBalls": "long_balls",
    "totalCrosses": "crosses", "accurateCrosses": "crosses_completed", "wonCorners": "corners",
    "totalTackles": "tackles", "interceptions": "interceptions", "foulsCommitted": "fouls",
    "saves": "saves", "blockedShots": "blocked_shots", "totalClearance": "clearances",
}


def _espn_team_stats(team_block):
    st = dict(EMPTY_STATS, attack_side=dict(EMPTY_STATS["attack_side"]))
    for s in team_block.get("statistics", []) or []:
        k = ESPN_STAT_MAP.get(s.get("name"))
        if k:
            st[k] = num(s.get("displayValue", s.get("value")))
    if st["pass_accuracy_pct"] is not None and st["pass_accuracy_pct"] <= 1.0:
        st["pass_accuracy_pct"] *= 100  # some feeds give 0.83
    return st


def espn_parse_summary(j, event_id=None):
    comp = (j.get("header", {}).get("competitions") or [{}])[0]
    stype = comp.get("status", {}).get("type", {})
    name = stype.get("name", "")
    if "EXTRA" in name or "SHOOTOUT" in name or "PENALT" in name:
        status = "ft" if stype.get("completed") else "live"
    else:
        status = None
    status = status or {"STATUS_SCHEDULED": "pre", "STATUS_FIRST_HALF": "live", "STATUS_SECOND_HALF": "live",
              "STATUS_HALFTIME": "ht", "STATUS_FULL_TIME": "ft", "STATUS_FINAL": "ft",
              "STATUS_IN_PROGRESS": "live", "STATUS_END_OF_REGULATION": "ft"}.get(name)
    if status is None:
        status = "ft" if stype.get("completed") else ("live" if stype.get("state") == "in" else "pre")
    minute = num(comp.get("status", {}).get("displayClock"))
    teams = {}
    for c in comp.get("competitors", []):
        ha = c.get("homeAway")
        tn = c.get("team", {}).get("displayName") or c.get("team", {}).get("name")
        teams[ha] = {"name": tn, "id": c.get("team", {}).get("id"), "is_rsl": same_team(tn, RSL_NAME),
                     "score": int(num(c.get("score"), 0))}
    stats = {"home": dict(EMPTY_STATS), "away": dict(EMPTY_STATS)}
    for tb in (j.get("boxscore", {}).get("teams") or []):
        tid = tb.get("team", {}).get("id")
        side = tb.get("homeAway") or next((k for k, v in teams.items() if v.get("id") == tid), None)
        if side in stats:
            stats[side] = _espn_team_stats(tb)
    events = []
    for e in (j.get("keyEvents") or []):
        t = (e.get("type", {}).get("text") or "").lower()
        typ = "goal" if "goal" in t else "card" if "card" in t else "sub" if "substitution" in t else None
        if not typ:
            continue
        parts = e.get("participants") or []
        events.append({"minute": num(e.get("clock", {}).get("displayValue"), 0), "type": typ,
                       "team": e.get("team", {}).get("displayName"),
                       "player": (parts[0].get("athlete", {}).get("displayName") if parts else None)})
    if not teams.get("home") or not teams.get("away"):
        raise ValueError("ESPN summary missing competitors")
    return {"match_id": str(event_id or comp.get("id", "")), "source": "espn", "fetched_at": now_iso(),
            "status": status, "minute": minute, "teams": teams, "stats": stats, "shots": [], "events": events,
            "date": comp.get("date"),
            "period": 1 if name == "STATUS_FIRST_HALF" else 2 if name == "STATUS_SECOND_HALF" else 3 if "EXTRA" in name else None}


def espn_summary(event_id):
    return espn_parse_summary(http_json(f"{ESPN}/summary", params={"event": event_id}), event_id)


def espn_scoreboard(start, end):
    """Return list of {id,date,home,away,state} for a date range (YYYYMMDD)."""
    j = http_json(f"{ESPN}/scoreboard", params={"dates": f"{start}-{end}", "limit": 500})
    out = []
    for ev in j.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        cs = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        if "home" not in cs or "away" not in cs:
            continue
        slug = (ev.get("season", {}) or {}).get("slug") or (j.get("leagues", [{}])[0].get("season", {}) or {}).get("type", {}).get("name") or ""
        stage = "playoff" if re.search(r"play-?off|post|cup|knockout|round", (slug + " " + (ev.get("name") or "") + " " + " ".join(n.get("headline", "") for n in (comp.get("notes") or []))).lower()) else "regular"
        out.append({"id": str(ev.get("id")), "date": ev.get("date"), "stage": stage, "season_slug": slug,
                    "home": cs["home"]["team"]["displayName"], "away": cs["away"]["team"]["displayName"],
                    "state": comp.get("status", {}).get("type", {}).get("state"),  # pre / in / post
                    "name": comp.get("status", {}).get("type", {}).get("name"),
                    "hs": int(num(cs["home"].get("score"), 0)), "as": int(num(cs["away"].get("score"), 0))})
    return out


def espn_season_events(year=SEASON):
    """All events in a season, fetched month by month to stay under feed limits."""
    out, seen = [], set()
    for m in range(1, 13):
        start = dt.date(year, m, 1)
        end = (dt.date(year + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1))
        try:
            for e in espn_scoreboard(start.strftime("%Y%m%d"), end.strftime("%Y%m%d")):
                if e["id"] not in seen:
                    seen.add(e["id"]); out.append(e)
        except Exception as ex:
            log_health("espn", False, f"scoreboard {start}: {ex}")
    return out


# ---------------------------------------------------------------- FotMob (best effort)
FOTMOB = "https://www.fotmob.com/api"


def fotmob_find_match(home, away, date_iso):
    d = date_iso[:10].replace("-", "")
    j = http_json(f"{FOTMOB}/matches", params={"date": d}, headers={"Referer": "https://www.fotmob.com/"})
    for lg in j.get("leagues", []):
        for m in lg.get("matches", []):
            if same_team(m.get("home", {}).get("name"), home) and same_team(m.get("away", {}).get("name"), away):
                return str(m.get("id"))
    raise LookupError("FotMob match not found")


def fotmob_summary(home, away, date_iso):
    mid = fotmob_find_match(home, away, date_iso)
    j = http_json(f"{FOTMOB}/matchDetails", params={"matchId": mid}, headers={"Referer": "https://www.fotmob.com/"})
    gen, cont = j.get("general", {}), j.get("content", {})
    hdr_teams = j.get("header", {}).get("teams") or [{}, {}]
    stats = {"home": dict(EMPTY_STATS), "away": dict(EMPTY_STATS)}
    key_map = {"BallPossesion": "possession_pct", "total_shots": "shots", "ShotsOnTarget": "shots_on_target",
               "expected_goals": "xg", "passes": "passes", "corners": "corners", "fouls": "fouls",
               "tackles_succeeded": "tackles", "interceptions": "interceptions", "keeper_saves": "saves",
               "blocked_shots": "blocked_shots", "Clearances": "clearances", "long_balls_accurate": "long_balls"}
    periods = cont.get("stats", {}).get("Periods", {})
    allp = periods.get("All", {}).get("stats", []) if periods else []
    for grp in allp:
        for s in grp.get("stats", []):
            k = key_map.get(s.get("key"))
            vals = s.get("stats")
            if k and isinstance(vals, list) and len(vals) == 2:
                stats["home"][k], stats["away"][k] = num(vals[0]), num(vals[1])
            elif s.get("key") == "accurate_passes" and isinstance(vals, list) and len(vals) == 2:
                pass
    shots = []
    for sh in (cont.get("shotmap", {}) or {}).get("shots", []) or []:
        shots.append({"team": "home" if sh.get("teamId") == gen.get("homeTeam", {}).get("id") else "away",
                      "minute": sh.get("min"), "x": sh.get("x"), "y": sh.get("y"),
                      "xg": sh.get("expectedGoals"), "outcome": sh.get("eventType")})
    st = gen.get("started") and not gen.get("finished")
    status = "ft" if gen.get("finished") else ("live" if st else "pre")
    if not any(v is not None for v in stats["home"].values()):
        raise ValueError("FotMob returned no stats")
    return {"match_id": mid, "source": "fotmob", "fetched_at": now_iso(), "status": status, "minute": None,
            "teams": {"home": {"name": gen.get("homeTeam", {}).get("name", home), "is_rsl": same_team(home, RSL_NAME),
                               "score": int(num(hdr_teams[0].get("score"), 0))},
                      "away": {"name": gen.get("awayTeam", {}).get("name", away), "is_rsl": same_team(away, RSL_NAME),
                               "score": int(num(hdr_teams[-1].get("score"), 0))}},
            "stats": stats, "shots": shots, "events": [], "date": date_iso}


# ---------------------------------------------------------------- API-Football (needs key)
APIF = "https://v3.football.api-sports.io"


def apif_summary(home, away, date_iso):
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError("API_FOOTBALL_KEY not set")
    h = {"x-apisports-key": key}
    j = http_json(f"{APIF}/fixtures", params={"league": 253, "season": SEASON, "date": date_iso[:10]}, headers=h)
    fx = None
    for f in j.get("response", []):
        if same_team(f["teams"]["home"]["name"], home) and same_team(f["teams"]["away"]["name"], away):
            fx = f; break
    if not fx:
        raise LookupError("API-Football fixture not found")
    fid = fx["fixture"]["id"]
    sj = http_json(f"{APIF}/fixtures/statistics", params={"fixture": fid}, headers=h)
    m = {"Ball Possession": "possession_pct", "Total Shots": "shots", "Shots on Goal": "shots_on_target",
         "Corner Kicks": "corners", "Fouls": "fouls", "Total passes": "passes", "Passes %": "pass_accuracy_pct",
         "expected_goals": "xg", "Goalkeeper Saves": "saves", "Blocked Shots": "blocked_shots"}
    stats = {"home": dict(EMPTY_STATS), "away": dict(EMPTY_STATS)}
    for blk in sj.get("response", []):
        side = "home" if same_team(blk["team"]["name"], home) else "away"
        for s in blk.get("statistics", []):
            k = m.get(s.get("type"))
            if k:
                stats[side][k] = num(s.get("value"))
    short = fx["fixture"]["status"]["short"]
    status = {"NS": "pre", "1H": "live", "2H": "live", "HT": "ht", "FT": "ft", "ET": "live", "PEN": "ft"}.get(short, "live")
    return {"match_id": str(fid), "source": "api-football", "fetched_at": now_iso(), "status": status,
            "minute": fx["fixture"]["status"].get("elapsed"),
            "period": 1 if short == "1H" else 2 if short == "2H" else None,
            "teams": {"home": {"name": home, "is_rsl": same_team(home, RSL_NAME), "score": int(fx["goals"]["home"] or 0)},
                      "away": {"name": away, "is_rsl": same_team(away, RSL_NAME), "score": int(fx["goals"]["away"] or 0)}},
            "stats": stats, "shots": [], "events": [], "date": date_iso}


# ---------------------------------------------------------------- ASA (xG overlay for season profiles)
ASA = "https://app.americansocceranalysis.com/api/v1/mls"


def asa_team_xg(year=SEASON):
    """Return {team_name: {xg_pg, xg_ag_pg, games}} or raise."""
    teams = {t["team_id"]: t.get("team_name") for t in http_json(f"{ASA}/teams")}
    rows = http_json(f"{ASA}/teams/xgoals", params={"season_name": str(year), "stage_name": "Regular Season"})
    out = {}
    for r in rows:
        g = num(r.get("count_games"), None) or num(r.get("games"), None)
        nm = teams.get(r.get("team_id"))
        if nm and g:
            out[nm] = {"xg_pg": num(r.get("xgoals_for")) / g, "xg_ag_pg": num(r.get("xgoals_against")) / g, "games": g}
    if not out:
        raise ValueError("ASA returned no xG rows")
    return out
