# RSL Tactics

A phone web app for watching Real Salt Lake. Every insight is Data, Meaning, Watch for, labeled Measured or Inference. Cost to run: $0.

Preview it with fake data (no setup): open `web/index.html?demo=1` through any static server, for example `cd web && python3 -m http.server`.

## Do these in order

1. **Create a GitHub account and a new public repo** (public repos get unlimited free Actions minutes). Upload this folder as the repo root.
2. **Turn on Pages:** repo Settings, Pages, Source = GitHub Actions.
3. **Allow the bot to push:** Settings, Actions, General, Workflow permissions = Read and write.
4. **Get a free API-Football key** at api-football.com (100 requests a day). Add it under Settings, Secrets and variables, Actions, as `API_FOOTBALL_KEY`. Optional, it is backup source 2.
5. **Run `verify-sources`** (Actions tab, Run workflow). Read the summary. This is the Phase 0 check that could not be done while building (see below). Send me the output and I will fix any parser that does not match.
6. **Run `weekly-profiles`** once by hand. It builds season profiles from every completed MLS match, the fixture list and the first matchup.
7. **Open the Pages URL on your iPhone,** Share, Add to Home Screen.
8. After that nothing is manual: fixtures refresh daily, profiles weekly, the matchup builds about 6 hours and 1 hour before kickoff, and live polling plus the halftime report run on their own.

## What was and was not verified

- **Verified (offline tests, `python tests/test_pipeline.py`, 17 pass):** parsing, rules engine, null handling, failover from FotMob to ESPN labeled "backup 1", halftime report built from the backup, all-sources-down keeps the last good data, no em dashes anywhere. UI checked at iPhone size with no JS errors or horizontal scroll.
- **Not verified:** the real endpoints. The build sandbox blocked ASA, ESPN, FotMob and API-Football at the network level. The ESPN box-score field names, ASA response fields and FotMob parsing are written from memory of those APIs. `verify-sources` tests all of them and saves ESPN's real stat names to `data/samples/`.
- **Most likely to need a fix:** FotMob (unofficial, has added request signing before). If it fails the app silently uses ESPN, which is what the fallback is for.

## Where data comes from

- **Season profiles:** every completed MLS match from ESPN box scores (cached in `data/cache/`), aggregated into per-game averages with league rank. ASA xG is added when its API answers. If ASA fails, xG cards hide.
- **Live and halftime:** FotMob, then ESPN, then API-Football. First success wins. The header shows which one and how old the data is.
- **Health:** `data/health.json`. The colored dots under the title show each source.

## Known gaps in the free data

- **Attack zones (left/center/right) and shot maps** only appear if FotMob supplies them. ESPN does not. Those sections hide when missing.
- **PPDA is approximate:** opponent passes divided by (tackles + interceptions + fouls). Cards using it are labeled Inference.
- **Key players by g+** is not built yet. ASA player data needs its own pull.
- **FBref** is not wired in. Add it only if `verify-sources` shows ASA or ESPN is missing something you want.
- **Progressive passes and field tilt** are in Learn Mode as definitions but not in the free feeds.

## Test the failover yourself

Actions tab, `live`, Run workflow, with a `match_id` of a recent RSL match (ESPN event id is in `data/schedule.json`) and `force_fail` = `fotmob`. The header should read "Live data: espn (backup 1)".

Locally: `FORCE_FAIL=fotmob python scripts/live.py --match-id ID`.

## Playoffs

RSL are the No. 9 seed in the West. The Wild Card is single elimination at Seattle on Thursday Nov 19, 10 pm ET (8 pm MT). If RSL win, Round One is a best-of-three.

- Playoff matches are tagged from the ESPN feed. Season norms and league ranks use **regular season games only**, but playoff results count in "last 5" form.
- The live window for a playoff match runs 210 minutes after kickoff so extra time and penalties are covered.
- A blue "Playoff match" banner shows on those games, and the game script adds the knockout context.
- `verify-sources` reports how many playoff-tagged events ESPN returns. If it shows zero in November, the tagging needs a tweak, so send me the output.
- Until a match is on the schedule the app shows **replay mode** (banner) with the most recent completed match.

## Layout

`scripts/` pipeline and rules engine. `data/` generated JSON. `web/` the app (PWA). `tests/` offline tests. `.github/workflows/` the schedules.

Rules live in `scripts/rules.py`. To change a threshold or add a card, edit there. Each rule lists its own condition text, which the app shows when you tap "Show the numbers and the rule".

## Notes

- GitHub's shortest cron is 5 minutes and it can run late. `live` starts every 10 minutes and polls 4 times, 2.5 minutes apart.
- Pages deploys after each data commit, so a poll appears on the site about a minute later.
