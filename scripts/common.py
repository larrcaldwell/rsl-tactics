"""Shared helpers: HTTP with retries, JSON IO, health logging, metric registry."""
import json, os, time, datetime as dt, re
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("RSL_DATA_DIR", os.path.join(ROOT, "data"))
CACHE = os.path.join(DATA, "cache")
UA = "Mozilla/5.0 (compatible; RSLTacticalApp/1.0; personal fan project)"
RSL_NAME = "Real Salt Lake"
LEAGUE_ESPN = "usa.1"
SEASON = int(os.environ.get("RSL_SEASON", dt.date.today().year))


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def path(*p):
    return os.path.join(DATA, *p)


def read_json(p, default=None):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, p)


def log_health(source, ok, detail=""):
    """Record per-source success or failure in data/health.json."""
    h = read_json(path("health.json"), {"sources": {}, "events": []})
    s = h["sources"].setdefault(source, {"ok": None, "last_ok": None, "last_fail": None, "detail": ""})
    s["ok"] = ok
    s["detail"] = str(detail)[:300]
    s["last_ok" if ok else "last_fail"] = now_iso()
    h["events"] = (h["events"] + [{"t": now_iso(), "source": source, "ok": ok, "detail": str(detail)[:200]}])[-60:]
    h["updated_at"] = now_iso()
    write_json(path("health.json"), h)


def http_json(url, params=None, headers=None, retries=2, timeout=20, pause=0.0):
    """GET and parse JSON. Raises on failure so callers can fall back."""
    hdr = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        hdr.update(headers)
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=hdr, timeout=timeout)
            if r.status_code == 200:
                if pause:
                    time.sleep(pause)
                return r.json()
            last = RuntimeError(f"HTTP {r.status_code} for {url}")
            if r.status_code in (401, 403, 404):
                break
        except Exception as e:  # network or JSON error
            last = e
        time.sleep(1.5 * (i + 1))
    raise last


def num(x, default=None):
    """Parse numbers like '54.2', '54%', '12/20' (returns first), None-safe."""
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r"-?\d+(?:\.\d+)?", str(x))
    return float(m.group()) if m else default


# Metric registry: key, label, decimals, glossary term, "good" direction (for wording only)
METRICS = {
    "poss":        dict(label="Possession %", d=1, term="possession"),
    "passes":      dict(label="Passes", d=0, term="passes"),
    "pass_pct":    dict(label="Pass accuracy %", d=1, term="pass_accuracy"),
    "long_pct":    dict(label="Long ball share of passes %", d=1, term="long_ball_share"),
    "shots":       dict(label="Shots", d=1, term="shots"),
    "sot":         dict(label="Shots on target", d=1, term="sot"),
    "crosses":     dict(label="Crosses", d=1, term="crosses"),
    "cross_pct":   dict(label="Cross accuracy %", d=1, term="cross_accuracy"),
    "corners":     dict(label="Corners", d=1, term="corners"),
    "tackles":     dict(label="Tackles", d=1, term="tackles"),
    "interceptions": dict(label="Interceptions", d=1, term="interceptions"),
    "fouls":       dict(label="Fouls", d=1, term="fouls"),
    "goals":       dict(label="Goals", d=2, term="goals"),
    "xg":          dict(label="xG", d=2, term="xg"),
    "shots_ag":    dict(label="Shots conceded", d=1, term="shots"),
    "sot_ag":      dict(label="Shots on target conceded", d=1, term="sot"),
    "crosses_ag":  dict(label="Crosses conceded", d=1, term="crosses"),
    "corners_ag":  dict(label="Corners conceded", d=1, term="corners"),
    "goals_ag":    dict(label="Goals conceded", d=2, term="goals"),
    "xg_ag":       dict(label="xG conceded", d=2, term="xg"),
    "ppda":        dict(label="PPDA (approx)", d=1, term="ppda"),
    "conv":        dict(label="Shot conversion %", d=1, term="conversion"),
}
