"""Phase 0: probe every data source with real calls and report what works.
Run on GitHub Actions (workflow: verify-sources) or locally. Writes data/source_report.json,
data/health.json, and a trimmed ESPN sample to data/samples/ so parsers can be checked.
"""
import datetime as dt, traceback
from common import *
import sources as S

report = []


def probe(name, fn):
    try:
        detail = fn()
        report.append({"source": name, "ok": True, "detail": detail}); log_health(name.split(":")[0], True, detail)
    except Exception as ex:
        report.append({"source": name, "ok": False, "detail": f"{type(ex).__name__}: {ex}"})
        log_health(name.split(":")[0], False, ex)


def p_asa():
    t = http_json(f"{S.ASA}/teams")
    x = S.asa_team_xg()
    return f"{len(t)} teams, xG rows for {len(x)} teams"


def p_espn_board():
    ev = S.espn_season_events()
    post = [e for e in ev if e["state"] == "post"]
    po = [e for e in ev if e.get("stage") == "playoff"]
    slugs = sorted({e.get("season_slug") or "?" for e in ev})
    return f"{len(ev)} events, {len(post)} completed, {len(po)} tagged playoff, season slugs seen: {slugs}"


def p_espn_summary():
    ev = [e for e in S.espn_season_events() if e["state"] == "post"]
    if not ev:
        raise RuntimeError("no completed events")
    e = ev[-1]
    raw = http_json(f"{S.ESPN}/summary", params={"event": e["id"]})
    names = sorted({s.get("name") for tb in raw.get("boxscore", {}).get("teams", []) for s in tb.get("statistics", [])})
    write_json(path("samples", "espn_stat_names.json"), {"event": e, "stat_names": names})
    snap = S.espn_parse_summary(raw, e["id"])
    got = {k: v for k, v in snap["stats"]["home"].items() if v is not None and k != "attack_side"}
    missing = [k for k in ("possession_pct", "shots", "passes", "crosses", "long_balls", "tackles") if k not in got]
    return f"{e['home']} v {e['away']}: parsed {len(got)} stats; missing {missing or 'none'}; raw stat names saved"


def p_fotmob():
    ev = [e for e in S.espn_season_events() if e["state"] == "post"]
    e = ev[-1]
    s = S.fotmob_summary(e["home"], e["away"], e["date"])
    got = [k for k, v in s["stats"]["home"].items() if v is not None and k != "attack_side"]
    return f"parsed {len(got)} stats, {len(s['shots'])} shots (shot map {'yes' if s['shots'] else 'no'}), xG {'yes' if s['stats']['home'].get('xg') is not None else 'no'}"


def p_apif():
    if not os.environ.get("API_FOOTBALL_KEY"):
        raise RuntimeError("API_FOOTBALL_KEY secret not set (optional backup)")
    j = http_json(f"{S.APIF}/status", headers={"x-apisports-key": os.environ["API_FOOTBALL_KEY"]})
    r = j.get("response", {}).get("requests", {})
    return f"key ok, requests today {r.get('current')}/{r.get('limit_day')}"


probe("asa: teams + xgoals", p_asa)
probe("espn: season scoreboard", p_espn_board)
probe("espn: match summary + stat names", p_espn_summary)
probe("fotmob: match details", p_fotmob)
probe("api-football: status", p_apif)
write_json(path("source_report.json"), {"generated_at": now_iso(), "results": report})
for r in report:
    print(("OK   " if r["ok"] else "FAIL ") + r["source"] + " :: " + r["detail"])
