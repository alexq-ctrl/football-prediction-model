"""Pre-match squad availability. Injury listings are information, not player-value estimates."""
from datetime import datetime, timezone
from math import isfinite

def apply_squad_adjustments(home_xg, away_xg, home_attack=1.0, away_attack=1.0,
                            home_defense=1.0, away_defense=1.0):
    factors = (home_attack, away_attack, home_defense, away_defense)
    if any(not isfinite(float(v)) or not 0.8 <= float(v) <= 1.2 for v in factors):
        raise ValueError("Squad factors must be finite and between 0.8 and 1.2")
    return home_xg * home_attack * away_defense, away_xg * away_attack * home_defense

def find_fixture(request, home_id, away_id, kickoff):
    """Find a scheduled fixture using API-Football team IDs."""

    from datetime import timedelta

    kickoff_utc = kickoff.astimezone(timezone.utc)

    start_date = (kickoff_utc - timedelta(days=1)).date().isoformat()
    end_date = (kickoff_utc + timedelta(days=1)).date().isoformat()

    season = (
        kickoff_utc.year
        if kickoff_utc.month >= 7
        else kickoff_utc.year - 1
    )

    data = request(
        "/fixtures",
        {
            "team": home_id,
            "season": season,
            "from": start_date,
            "to": end_date,
        },
    )

    if not isinstance(data, list):
        return None, "Fixture lookup unavailable (API error or unsupported access)."

    for item in data:
        teams = item.get("teams") or {}

        home = (teams.get("home") or {}).get("id")
        away = (teams.get("away") or {}).get("id")

        if home != home_id or away != away_id:
            continue

        fixture = item.get("fixture") or {}
        fixture_date = fixture.get("date")

        if not fixture_date:
            continue

        try:
            actual_kickoff = datetime.fromisoformat(
                fixture_date.replace("Z", "+00:00")
            )

            time_difference = abs(
                (actual_kickoff - kickoff_utc).total_seconds()
            )

            if time_difference <= 24 * 3600:
                return fixture.get("id"), None

        except ValueError:
            continue

    return None, "No matching scheduled fixture found near that kickoff."

def fetch_fixture_absences(request, fixture_id, home_id, away_id):
    data = request("/injuries", {"fixture": fixture_id})
    if not isinstance(data, list):
        return None, "Injury endpoint unavailable or not included in the API plan."
    result = {home_id: [], away_id: []}
    for item in data:
        team_id = (item.get("team") or {}).get("id")
        if team_id not in result:
            continue
        player = item.get("player") or {}
        result[team_id].append({
            "name": player.get("name") or "Unknown player",
            "status": player.get("type") or "Unknown",
            "reason": player.get("reason") or "Unspecified",
        })
    return result, None

def display_squad_report(request, home_id, away_id, home_name, away_name, kickoff):
    """Show only fixture-specific data; empty API responses are not proof of full fitness."""
    print("\n--- Squad availability (API-Football) ---")
    if kickoff <= datetime.now(timezone.utc):
        print("No current squad lookup for past kickoffs; archived reports may not reflect pre-match knowledge.")
        return
    fixture_id, error = find_fixture(request, home_id, away_id, kickoff)
    if error:
        print(error)
        return
    absences, error = fetch_fixture_absences(request, fixture_id, home_id, away_id)
    if error:
        print(error)
        return
    for team_id, name in ((home_id, home_name), (away_id, away_name)):
        entries = absences[team_id]
        print(f"{name}: {len(entries)} reported unavailable/questionable players")
        if not entries:
            print("  No reports returned; availability is unconfirmed.")
        for player in entries:
            print(f"  {player['name']}: {player['status']} — {player['reason']}")
    print("Reported absences do NOT automatically change expected goals: player impact is not yet estimated.")
