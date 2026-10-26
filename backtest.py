"""Leakage-aware walk-forward evaluation of Phase 3 + Poisson club model.

Uses Football-Data competition matches only; does NOT use historical API-Football
blending. Therefore results are for the Phase 3/current-data variant, not an
exact retrospective replay of main.py's mixed-provider live predictions.
"""
import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from main import (football_data_request, normalize_football_data_matches,
                  calculate_expected_goals, build_score_matrix,
                  match_result_probabilities)
from opponent_strength import run_opponent_strength_model
from match_context import apply_match_context
from draw_model import dixon_coles_matrix


def valid_match(m):
    try:
        return (m["goals"]["home"] is not None and
                m["goals"]["away"] is not None and
                m["teams"]["home"]["id"] != m["teams"]["away"]["id"] and
                bool(m["fixture"]["date"]))
    except (KeyError, TypeError):
        return False


def utc_date(m):
    return datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00")).astimezone(timezone.utc)


def load_api_matches(competition, seasons):
    all_matches = []
    for season in seasons:
        response = football_data_request(
            f"/competitions/{competition}/matches",
            {"season": season, "status": "FINISHED"},
        )
        if response is None:
            print(f"Warning: season {season} was unavailable (check API access).")
            continue
        all_matches.extend(normalize_football_data_matches(response.get("matches", [])))
    return all_matches


def evaluate(matches, min_team_matches=8, max_team_matches=30, max_goals=10):
    """Walk-forward: predictions see only games with an earlier kickoff timestamp."""
    if min_team_matches < 1 or max_team_matches < min_team_matches:
        raise ValueError("Expected 1 <= min_team_matches <= max_team_matches")
    unique = {}
    for m in matches:
        if not valid_match(m):
            continue
        try:
            stamp = utc_date(m)
        except ValueError:
            continue
        h, a = m["teams"]["home"]["id"], m["teams"]["away"]["id"]
        unique[(stamp, h, a)] = m
    ordered = sorted(unique.values(), key=utc_date)
    history = []
    predictions = []
    skipped = Counter()
    index = 0
    while index < len(ordered):
        kickoff = utc_date(ordered[index])
        end = index
        while end < len(ordered) and utc_date(ordered[end]) == kickoff:
            end += 1
        # All games at the same kickoff are evaluated BEFORE adding any of them.
        for target in ordered[index:end]:
            hid = target["teams"]["home"]["id"]
            aid = target["teams"]["away"]["id"]
            home_history = [m for m in history if hid in (m["teams"]["home"]["id"], m["teams"]["away"]["id"])][-max_team_matches:]
            away_history = [m for m in history if aid in (m["teams"]["home"]["id"], m["teams"]["away"]["id"])][-max_team_matches:]
            if min(len(home_history), len(away_history)) < min_team_matches:
                skipped["insufficient_history"] += 1
                continue
            phase3 = run_opponent_strength_model(history, home_history, away_history, hid, aid)
            hs, aws = phase3["home_stats"], phase3["away_stats"]
            if hs is None or aws is None:
                skipped["missing_stats"] += 1
                continue
            home_xg, away_xg = calculate_expected_goals(hs, aws)
            home_xg, away_xg, _, _ = apply_match_context(
                home_xg, away_xg, history, hid, aid, kickoff
            )
            matrix = dixon_coles_matrix(
                build_score_matrix(home_xg, away_xg, max_goals=max_goals),
                home_xg, away_xg,
            )
            home_p, draw_p, away_p = match_result_probabilities(matrix)
            hg, ag = target["goals"]["home"], target["goals"]["away"]
            actual = "H" if hg > ag else "A" if hg < ag else "D"
            probs = {"H": home_p, "D": draw_p, "A": away_p}
            predictions.append({
                "date_utc": kickoff.isoformat(),
                "home_team": target["teams"]["home"].get("name", str(hid)),
                "away_team": target["teams"]["away"].get("name", str(aid)),
                "home_goals": hg, "away_goals": ag,
                "home_xg": round(home_xg, 4), "away_xg": round(away_xg, 4),
                "p_home": round(home_p, 8), "p_draw": round(draw_p, 8), "p_away": round(away_p, 8),
                "actual": actual, "predicted": max(probs, key=probs.get),
                "history_matches": len(history),
                "home_elo": round(phase3["comparison"]["home_rating"], 2),
                "away_elo": round(phase3["comparison"]["away_rating"], 2),
            })
        history.extend(ordered[index:end])
        index = end
    return predictions, dict(skipped), len(ordered)


def metrics(rows):
    if not rows:
        return None
    correct = brier = logloss = 0.0
    for row in rows:
        correct += row["predicted"] == row["actual"]
        probs = {"H": row["p_home"], "D": row["p_draw"], "A": row["p_away"]}
        brier += sum((probs[k] - (1 if row["actual"] == k else 0))**2 for k in probs)
        logloss -= math.log(max(1e-15, probs[row["actual"]]))
    n = len(rows)
    return {"evaluated_matches": n, "accuracy": correct / n,
            "brier_3class": brier / n, "log_loss": logloss / n}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition", default="PL", help="Football-Data competition code")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2025, 2026])
    parser.add_argument("--input-json", type=Path, help="Optional offline Football-Data JSON (list or {'matches': [...]})")
    parser.add_argument("--min-matches", type=int, default=8)
    parser.add_argument("--window", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("backtest_results.csv"))
    args = parser.parse_args()
    if args.input_json:
        payload = json.loads(args.input_json.read_text())
        raw = payload if isinstance(payload, list) else payload["matches"]
        matches = raw if raw and "fixture" in raw[0] else normalize_football_data_matches(raw)
    else:
        from main import FOOTBALL_DATA_KEY
        if not FOOTBALL_DATA_KEY:
            parser.error("Set FOOTBALL_DATA_KEY in your .env, or use --input-json")
        matches = load_api_matches(args.competition, args.seasons)
    if not matches:
        parser.error("No matches found. Check competition/season access or input JSON.")
    rows, skipped, total = evaluate(matches, args.min_matches, args.window)
    print(f"Completed unique matches loaded: {total}")
    print(f"Skipped: {skipped}")
    if not rows:
        print("No predictions evaluated. Try --min-matches 3 or more seasons.")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(metrics(rows), indent=2))
    print(f"Saved {len(rows)} predictions to {args.output}")
    print("Note: this tests the current-data Phase 3 model, not historical API-Football blending.")

if __name__ == "__main__":
    main()
