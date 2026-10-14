#!/usr/bin/env python3
"""
espn_weekly_pull.py - data-layer sketch for a weekly "who scored what, on which day" summary.

STATUS: partly verified against ESPN's raw roster response (see "VERIFIED" notes below).
Everything else is still from memory until `--discover` and `--week` have been run against it.

READ-ONLY: this only issues GET requests. It never changes your team.

Setup:
    pip install -r requirements.txt
    $env:ESPN_S2   = '...'       # espn_s2 cookie from a logged-in browser (PowerShell)
    $env:ESPN_SWID = '{...}'     # SWID cookie (keep the braces)
    # optional: ESPN_LEAGUE_ID (defaults to your league), ESPN_YEAR (defaults to 2027)

Usage:
    python espn_weekly_pull.py --discover     # slot/stat ids, scoring items, history check, box score probe, raw samples
    python espn_weekly_pull.py --week 2       # writes data/week_2.json (defaults to current week)
    python espn_weekly_pull.py --auto         # nightly mode: the previous week (to finish it) and the current one
"""
import argparse
import collections
import datetime as dt
import json
import os
import time
from pathlib import Path

import requests

LEAGUE_ID = os.environ.get("ESPN_LEAGUE_ID", "849447669")
YEAR = os.environ.get("ESPN_YEAR", "2027")  # ESPN labels the 2026-27 season as 2027
BASE = (
    f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/"
    f"seasons/{YEAR}/segments/0/leagues/{LEAGUE_ID}"
)
try:
    COOKIES = {"espn_s2": os.environ["ESPN_S2"], "SWID": os.environ["ESPN_SWID"]}
except KeyError as e:
    raise SystemExit(f"Environment variable {e.args[0]} is not set (see Setup in the docstring).")
CACHE, OUT, DATA = Path("cache"), Path("out"), Path("data")  # raw responses, scratch samples, saved weeks
for folder in (CACHE, OUT, DATA):
    folder.mkdir(exist_ok=True)

# Scoring period 1 fell on this date (verified against the app for days 7 to 16). Periods are
# consecutive days, so this fixes every day's date without trusting the clock of whatever machine
# runs the script.
FIRST_DAY = dt.date(2026, 9, 29)

# VERIFIED from the roster dump: each player's `eligibleSlots` lists 3 (all forwards), 4 (D only),
# 5 (G only), 6 and 7 and 8 (all skaters), with goalies eligible for 7 and 8 but NOT 6. So 6 is
# UTIL (skaters only), 7 is BE, 8 is IR. League-wide counts match the roster setup
# (7 teams: 7 C, 7 LW, 7 RW, 21 F, 28 D, 7 UTIL).
SLOT_NAMES = {0: "C", 1: "LW", 2: "RW", 3: "F", 4: "D", 5: "G", 6: "UTIL", 7: "BE", 8: "IR"}
BENCH_SLOTS = {7, 8}  # BE and IR: their points don't count
# VERIFIED from the roster dumps (defaultPositionId): 1 C, 2 LW, 3 RW, 4 D, 5 G.
POS_NAMES = {1: "C", 2: "LW", 3: "RW", 4: "D", 5: "G"}

# VERIFIED: ESPN's scoring items (--discover) list exactly these ids with the points you described,
# and all 29 sampled day stat lines reconcile to ESPN's appliedTotal. Only the PPP/SHP split is
# inferred: 38 and 39 are the two remaining 0.5 items and Dahlin's PP point sits on 38.
# 3 (SA) and 11 (SV%) don't score but are kept for display. Unlabeled ids are shown by number.
STAT_NAMES = {
    "13": "G", "14": "A", "38": "PPP", "39": "SHP", "29": "SOG", "31": "HIT", "32": "BLK",
    "1": "W", "4": "GA", "6": "SV", "7": "SO", "9": "OTL", "3": "SA", "11": "SV%",
}


def fetch(views, scoring_period=None, cache_name=None, extra=None):
    """GET one or more ESPN 'views'. If cache_name is given, the response is cached on disk
    and reused forever, so only use it for days that are finished."""
    path = CACHE / f"{cache_name}.json" if cache_name else None
    if path and path.exists():
        return json.loads(path.read_text())

    params = [("view", v) for v in views]
    if scoring_period is not None:
        params.append(("scoringPeriodId", scoring_period))
    params += extra or []

    r = requests.get(BASE, params=params, cookies=COOKIES, timeout=30)
    if r.status_code in (401, 403):
        raise SystemExit("ESPN rejected the cookies. Refresh espn_s2 and SWID from your browser.")
    r.raise_for_status()
    data = r.json()

    if path:
        path.write_text(json.dumps(data))
    time.sleep(0.3)  # be polite to an unofficial API
    return data


def league_info():
    """Team names, current scoring period (a day), current week, and scoring items."""
    d = fetch(["mSettings", "mTeam"])
    teams = {
        t["id"]: (t.get("name") or f'{t.get("location", "")} {t.get("nickname", "")}').strip()
        for t in d["teams"]
    }
    current_sp = d["scoringPeriodId"]
    current_week = d["status"]["currentMatchupPeriod"]
    # NOTE: settings.scheduleSettings.matchupPeriods looks like it lists each week's days but doesn't
    # (week 2 maps to [2], while its real days are 7-13). Days come from the matchup data instead.
    # FROM MEMORY: [{"statId": 13, "points": 2.0, ...}, ...]. Empty list if the path is wrong.
    items = d["settings"].get("scoringSettings", {}).get("scoringItems", [])
    return teams, current_sp, current_week, items


def matchups_for(week):
    """Who plays whom this week, plus ESPN's own per-day totals (used as a sanity check)."""
    d = fetch(["mMatchupScore"])
    out = []
    for m in d["schedule"]:
        if m.get("matchupPeriodId") != week or "away" not in m:  # skip other weeks and byes
            continue
        out.append({
            "home": m["home"]["teamId"],
            "away": m["away"]["teamId"],
            "home_by_day": m["home"].get("pointsByScoringPeriod", {}),
            "away_by_day": m["away"].get("pointsByScoringPeriod", {}),
        })
    return out


def day_stats(player, sp):
    """The player's stat line for one scoring period, or None if they didn't play.

    VERIFIED: entries with statSplitTypeId 5 and statSourceId 0 are per-day actuals, and a player
    only has one for days they played. The response can also carry other days (e.g. asking for
    day 14 returned day-13 lines for some players), so always filter on scoringPeriodId.
    """
    return next(
        (s for s in player.get("stats", [])
         if s.get("scoringPeriodId") == sp
         and s.get("statSplitTypeId") == 5
         and s.get("statSourceId") == 0),
        None,
    )


def roster_day(sp, final, show=None):
    """Every team's roster for one day: player, lineup slot, and that day's fantasy points + stat line.

    UNVERIFIED: that mRoster with scoringPeriodId returns the lineup as it stood on that day.
    `--discover` runs a check for this. If it returns today's lineup instead, switch to the box
    score view (view=mBoxscore plus matchupPeriodId), which is what the app's Box Score screen uses.
    `show` is a set of stat ids worth keeping; None keeps every non-zero stat.
    """
    d = fetch(["mRoster"], sp, cache_name=f"roster_{sp}" if final else None)
    rows = {}
    for t in d["teams"]:
        players = []
        for e in t["roster"]["entries"]:
            p = e["playerPoolEntry"]["player"]
            day = day_stats(p, sp)
            stats = (day or {}).get("stats", {})
            # VERIFIED across 268 NHL-team-days: a team's players either ALL have an entry for a day
            # or none do. No entry = the team had no game. An entry with every stat zero = the team
            # played but this player didn't (scratched, out, backup goalie). Anything else = played.
            # ESPN doesn't say WHY a player sat, and the injury fields below are a snapshot from when
            # the day was first pulled (cached forever after), not a per-game flag.
            if any(stats.values()):
                state = "played"
            elif not final:
                state = "pending"  # today: games may not have started, so empty means nothing yet
            else:
                state = "nogame" if day is None else "dnp"
            players.append({
                "id": p["id"],
                "player": p["fullName"],
                "pos": POS_NAMES.get(p.get("defaultPositionId"), "?"),
                "slot_id": e["lineupSlotId"],
                "slot": SLOT_NAMES.get(e["lineupSlotId"], str(e["lineupSlotId"])),
                "state": state,
                "injury": p.get("injuryStatus"),
                "points": round(day["appliedTotal"], 1) if day else 0.0,
                "stats": {
                    STAT_NAMES.get(k, k): v for k, v in stats.items()
                    if v and (show is None or k in show)
                },
            })
        rows[t["id"]] = players
    return rows


def check_history(current_sp, days=4):
    """Does mRoster + scoringPeriodId really return each day's lineup, or always today's?

    Fetches the last few days (uncached) and counts players whose slot differs between
    consecutive days. Any changes at all means it IS historical. Zero changes is inconclusive:
    either nobody touched a lineup, or ESPN is returning today's lineup every time.
    """
    sps = list(range(max(current_sp - days, 1), current_sp))
    lineups = {}
    for sp in sps:
        d = fetch(["mRoster"], sp)
        lineups[sp] = {
            (t["id"], e["playerId"]): e["lineupSlotId"]
            for t in d["teams"] for e in t["roster"]["entries"]
        }
    print("\nHistory check (players whose lineup slot changed between consecutive days):")
    for a, b in zip(sps, sps[1:]):
        both = lineups[a].keys() & lineups[b].keys()
        moved = sum(1 for k in both if lineups[a][k] != lineups[b][k])
        added = len(lineups[b].keys() - lineups[a].keys())
        print(f"  day {a} -> {b}: {moved} moved slots, {added} new to a roster")
    print("  (all zeros = inconclusive: compare one past day with the app's box score for that day)")


def probe_boxscore(current_sp, current_week):
    """UNVERIFIED: does the box score view carry a per-day "out" flag (the app's "O" next to a name)?

    The mRoster injury fields turned out to be a snapshot from request time, identical on every
    day, so they can't say who was out on a given day. This asks mBoxscore for yesterday and prints
    every injury/status-like field it finds, plus a trimmed raw sample for inspection.
    """
    sp = max(current_sp - 1, 1)
    wk = current_week
    for w in (current_week, current_week - 1):  # which week does `sp` belong to?
        if sp in {int(k) for m in matchups_for(w) for k in m["home_by_day"]}:
            wk = w
            break
    d = fetch(["mBoxscore"], sp, extra=[("matchupPeriodId", wk)])
    sched = [m for m in d.get("schedule", []) if m.get("matchupPeriodId") == wk and "away" in m]
    (OUT / "raw_boxscore_sample.json").write_text(json.dumps(sched[:1], indent=1))
    print(f"\nBox score probe (day {sp}, week {wk}): {len(sched)} matchups")
    if not sched:
        print("  nothing came back")
        return

    side = sched[0]["home"]
    boxes = [k for k, v in side.items() if isinstance(v, dict) and "entries" in v]
    print(f"  roster containers on a team: {boxes or 'none'}")
    print(f"  other keys on a team: {sorted(set(side) - set(boxes))}")

    flags, odd = collections.Counter(), []
    for m in sched:
        for s in ("home", "away"):
            for b in boxes:
                for e in m[s][b]["entries"]:
                    pool = e.get("playerPoolEntry", {})
                    p = pool.get("player", {})
                    found = {}
                    for level, obj in (("entry", e), ("pool", pool), ("player", p)):
                        for k, v in obj.items():
                            if not isinstance(v, (dict, list)) and (
                                    "injur" in k.lower() or "status" in k.lower()):
                                found[f"{level}.{k}"] = v
                    for k, v in found.items():
                        flags[(b, k, v)] += 1
                    if any(v not in ("NORMAL", "ACTIVE") for k, v in found.items() if "injuryStatus" in k):
                        odd.append((p.get("fullName"), b, e.get("lineupSlotId"), found))
    print("  injury/status fields (container, field, value): count")
    for (b, k, v), n in sorted(flags.items(), key=str):
        print(f"    {b} {k} = {v!r}: {n}")
    print("  players with a non-normal injuryStatus (first 10):")
    for name, b, slot, found in odd[:10]:
        print(f"    {name} [{b}, slot {slot}] {found}")
    print(f"  (trimmed raw sample in {OUT / 'raw_boxscore_sample.json'})")


def discover(current_sp, current_week, items):
    """Dump raw samples and print what's needed to label slots, stats and scoring."""
    sp = max(current_sp - 1, 1)  # yesterday, so there are real game stats to look at
    sample = fetch(["mRoster"], sp)
    (OUT / "raw_roster_sample.json").write_text(json.dumps(sample, indent=1))

    slots, stat_ids, day_lines = {}, {}, []
    for t in sample["teams"]:
        for e in t["roster"]["entries"]:
            p = e["playerPoolEntry"]["player"]
            slots.setdefault(e["lineupSlotId"], []).append(p["fullName"])
            day = day_stats(p, sp)
            if day:
                day_lines.append((p["fullName"], day))
                for k, v in day.get("stats", {}).items():
                    stat_ids.setdefault(k, (p["fullName"], v))

    print("lineupSlotId -> example players (label these in SLOT_NAMES; decide which are bench/IR):")
    for sid, names in sorted(slots.items()):
        print(f"  {sid} ({SLOT_NAMES.get(sid, '?')}): {', '.join(names[:3])}")

    print("\nstat id -> (example player, value). Match to a box score to fill STAT_NAMES:")
    for k, (name, v) in sorted(stat_ids.items(), key=lambda kv: int(kv[0])):
        print(f"  {k} ({STAT_NAMES.get(k, '?')}): {name} = {v}")

    # Scoring items say which stat ids count and for how much, which pins down PPP/SHP/SO/OTL.
    print("\nScoring items from league settings (statId: points):")
    if not items:
        print("  none found - settings.scoringSettings.scoringItems isn't where I remembered")
    else:
        pts = {str(i["statId"]): i["points"] for i in items}
        for i in sorted(items, key=lambda i: i["statId"]):
            rev = " (reverse item)" if i.get("isReverseItem") else ""
            print(f"  {i['statId']}: {i['points']:+} {STAT_NAMES.get(str(i['statId']), '?')}{rev}")
        bad = 0
        for name, day in day_lines:
            calc = sum(pts.get(k, 0) * v for k, v in day.get("stats", {}).items())
            if abs(calc - day["appliedTotal"]) > 0.05:
                bad += 1
                print(f"  MISMATCH {name}: computed {calc:.2f} vs ESPN {day['appliedTotal']:.2f}")
        print(f"  reconcile: {len(day_lines) - bad}/{len(day_lines)} day stat lines match ESPN's total")

    check_history(current_sp)

    # One finished week of matchups, to confirm pointsByScoringPeriod exists.
    wk = max(current_week - 1, 1)
    sched = [m for m in fetch(["mMatchupScore"])["schedule"] if m.get("matchupPeriodId") == wk]
    (OUT / "raw_matchup_sample.json").write_text(json.dumps(sched[:2], indent=1))
    side = sched[0]["home"] if sched else {}
    print(f"\nmatchup (week {wk}) home keys: {sorted(side.keys())}")
    print(f"  pointsByScoringPeriod present: {'pointsByScoringPeriod' in side}")

    probe_boxscore(current_sp, current_week)

    print(f"\nRaw samples saved to {OUT / 'raw_roster_sample.json'} and {OUT / 'raw_matchup_sample.json'}")


def date_of(sp):
    """ESPN scoring period (a day) -> calendar date as 'YYYY-MM-DD'."""
    return (FIRST_DAY + dt.timedelta(days=sp - 1)).isoformat()


def frozen_rosters(week, current_sp):
    """Rosters already saved in data/week_N.json for days that are safely finished.

    A runner on GitHub starts empty every night, so the on-disk response cache can't be relied on.
    Instead, days older than yesterday are reused from the saved week file and never fetched again.
    Today and yesterday are always refetched: today is still changing, and yesterday's final stats
    can land after the morning pull. Returns {(scoring period, team id): players}.
    """
    path = DATA / f"week_{week}.json"
    if not path.exists():
        return {}
    frozen = {}
    for m in json.loads(path.read_text(encoding="utf-8"))["matchups"]:
        for sp, day in m["days"].items():
            sp = int(sp)
            if day.get("future") or day.get("today") or sp > current_sp - 2:
                continue
            for side in ("home", "away"):
                players = day[side]["players"]
                if players and "state" in players[0]:  # saved in the current format
                    frozen[(sp, m[side])] = players
    return frozen


def pull_week(week, teams, current_sp, current_week, items):
    show = {str(i["statId"]) for i in items if i.get("points")} | set(STAT_NAMES) or None

    # VERIFIED: a week's days are the keys of each matchup's pointsByScoringPeriod (week 2 = days 7-13).
    matchups = matchups_for(week)
    day_ids = {int(k) for m in matchups for k in (*m["home_by_day"], *m["away_by_day"])}
    if week == current_week:
        day_ids.add(current_sp)  # today may not have points yet

    frozen = frozen_rosters(week, current_sp)
    tids = [m[side] for m in matchups for side in ("home", "away")]
    days = {}
    for sp in sorted(day_ids):
        if sp > current_sp:
            continue  # future days have nothing to show
        if all((sp, t) in frozen for t in tids):
            days[sp] = {t: frozen[(sp, t)] for t in tids}
        else:
            days[sp] = roster_day(sp, final=(sp < current_sp), show=show)  # today stays uncached

    # Weeks run Monday to Sunday (confirmed for weeks 2 and 3; week 1 was a short week that also
    # ended on a Sunday), so pad the current week out to its Sunday with placeholder days. That keeps
    # the page layout the same all week. Finished weeks keep the days ESPN actually reports.
    future = []
    if days and week >= current_week:
        last = max(days)
        future = [last + i for i in range(1, 7 - dt.date.fromisoformat(date_of(last)).weekday())]

    result = {"week": week, "teams": teams, "matchups": []}
    for m in matchups:
        entry = {"home": m["home"], "away": m["away"], "days": {}}
        for sp, rosters in days.items():
            day = {"date": date_of(sp), "today": sp == current_sp}
            for side in ("home", "away"):
                tid = m[side]
                pl = rosters[tid]
                active = sum(p["points"] for p in pl if p["slot_id"] not in BENCH_SLOTS)
                bench = sum(p["points"] for p in pl if p["slot_id"] in BENCH_SLOTS)
                reported = m[f"{side}_by_day"].get(str(sp))
                day[side] = {
                    "players": pl,
                    "active_pts": round(active, 1),
                    "bench_pts": round(bench, 1),   # the "points left on the bench" number
                    "espn_reported": reported,
                }
                # Sanity check: our active total should match ESPN's daily team total.
                if BENCH_SLOTS and reported is not None and abs(active - reported) > 0.15:
                    print(f"WARN week {week}, {teams[tid]}, day {sp}: computed {active:.1f} vs ESPN {reported}")
            entry["days"][sp] = day
        for sp in future:  # placeholders: no rosters or points, just the date
            blank = {"players": [], "active_pts": 0.0, "bench_pts": 0.0, "espn_reported": None}
            entry["days"][sp] = {"date": date_of(sp), "future": True, "home": dict(blank), "away": dict(blank)}
        result["matchups"].append(entry)

    out_path = DATA / f"week_{week}.json"
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"Wrote {out_path} ({len(frozen) // max(len(tids), 1)} finished day(s) reused from the saved file)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, help="matchup period; defaults to the current one")
    ap.add_argument("--auto", action="store_true",
                    help="nightly mode: the previous week (to finish it) and the current week")
    ap.add_argument("--discover", action="store_true")
    args = ap.parse_args()

    teams, current_sp, current_week, items = league_info()

    if args.discover:
        discover(current_sp, current_week, items)
        return

    if args.week:
        weeks = [args.week]
    elif args.auto:
        weeks = [current_week - 1, current_week]
    else:
        weeks = [current_week]
    for week in weeks:
        if week >= 1:
            pull_week(week, teams, current_sp, current_week, items)


if __name__ == "__main__":
    main()
