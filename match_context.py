"""Fixture-derived match context. Only use completed matches before target kickoff."""
from datetime import datetime, timezone
from math import exp

def as_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

def team_context(matches, team_id, kickoff, lookback_days=14):
    now = as_utc(kickoff) if isinstance(kickoff, str) else kickoff
    previous = sorted(
        (as_utc(m["fixture"]["date"]) for m in matches
         if m["teams"]["home"]["id"] == team_id or m["teams"]["away"]["id"] == team_id
         if as_utc(m["fixture"]["date"]) < now),
        reverse=True,
    )
    if not previous:
        return {"rest_days": None, "matches_last_7": 0, "matches_last_14": 0, "factor": 1.0}
    rest = (now - previous[0]).total_seconds() / 86400
    count7 = sum((now - d).total_seconds() <= 7 * 86400 for d in previous)
    count14 = sum((now - d).total_seconds() <= lookback_days * 86400 for d in previous)
    # Small heuristic adjustments, deliberately capped. Validate by backtesting.
    penalty = min(0.07, max(0, 3 - rest) * 0.018 + max(0, count7 - 2) * 0.012)
    return {"rest_days": round(rest, 2), "matches_last_7": count7,
            "matches_last_14": count14, "factor": 1 - penalty}

def apply_match_context(home_xg, away_xg, matches, home_id, away_id, kickoff):
    home = team_context(matches, home_id, kickoff)
    away = team_context(matches, away_id, kickoff)
    # Fatigue impacts attacking output, not match-result probabilities directly.
    return home_xg * home["factor"], away_xg * away["factor"], home, away
