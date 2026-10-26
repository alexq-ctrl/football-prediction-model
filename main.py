import math
import os
import requests

from datetime import datetime, timezone
from dotenv import load_dotenv

from opponent_strength import run_opponent_strength_model
from match_context import apply_match_context
from squad_model import apply_squad_adjustments, display_squad_report
from draw_model import dixon_coles_matrix

load_dotenv()

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY")

API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
API_FOOTBALL_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}
FOOTBALL_DATA_HEADERS = {"X-Auth-Token": FOOTBALL_DATA_KEY}


def api_football_request(endpoint, params=None):
    url = API_FOOTBALL_BASE_URL + endpoint
    try:
        response = requests.get(url, headers=API_FOOTBALL_HEADERS, params=params, timeout=20)
    except requests.RequestException as exc:
        print(f"API-Football connection error: {exc}")
        return None
    if response.status_code != 200:
        print(f"API-Football request failed: {response.status_code}")
        try:
            print(response.json())
        except ValueError:
            print(response.text)
        return None
    data = response.json()
    if data.get("errors"):
        print("API-Football returned an error:")
        print(data["errors"])
        return None
    return data.get("response", [])


def football_data_request(endpoint, params=None):
    url = FOOTBALL_DATA_BASE_URL + endpoint
    try:
        response = requests.get(url, headers=FOOTBALL_DATA_HEADERS, params=params, timeout=20)
    except requests.RequestException as exc:
        print(f"Football-Data connection error: {exc}")
        return None
    if response.status_code != 200:
        print(f"Football-Data request failed: {response.status_code}")
        try:
            print(response.json())
        except ValueError:
            print(response.text)
        return None
    try:
        return response.json()
    except ValueError:
        print("Football-Data returned invalid JSON.")
        return None


def find_api_football_team(team_name):
    data = api_football_request("/teams", {"search": team_name})
    if not data:
        return None
    print("\nAPI-Football teams found:")
    for i, item in enumerate(data[:10], start=1):
        team = item["team"]
        print(f"{i}. {team['name']} (ID: {team['id']}, Country: {team.get('country', 'Unknown')})")
    while True:
        try:
            choice = int(input("Choose the correct API-Football team: "))
            if 1 <= choice <= min(10, len(data)):
                return data[choice - 1]["team"]
        except ValueError:
            pass
        print("Please enter one of the numbers shown above.")


def find_football_data_team(team_name, competition_code):
    data = football_data_request(f"/competitions/{competition_code}/teams")
    if not data:
        return None
    teams = data.get("teams", [])
    search = team_name.lower().strip()
    matches = []
    for team in teams:
        names = {
            team.get("name", "").lower(),
            team.get("shortName", "").lower(),
            team.get("tla", "").lower(),
        }
        if any(search == name or search in name for name in names if name):
            matches.append(team)
    if not matches:
        print(f"No Football-Data team found for '{team_name}'.")
        return None
    print("\nFootball-Data teams found:")
    for i, team in enumerate(matches, start=1):
        print(f"{i}. {team['name']} (ID: {team['id']})")
    while True:
        try:
            choice = int(input("Choose the correct Football-Data team: "))
            if 1 <= choice <= len(matches):
                return matches[choice - 1]
        except ValueError:
            pass
        print("Please enter one of the numbers shown above.")


def get_api_football_historical_matches(team_id, seasons=(2022, 2023, 2024), number_of_matches=20):
    all_matches = []
    for season in seasons:
        data = api_football_request(
            "/fixtures",
            {"team": team_id, "season": season, "status": "FT"},
        )
        if data:
            all_matches.extend(data)
    all_matches.sort(key=lambda match: match["fixture"]["date"], reverse=True)
    return all_matches[:number_of_matches]


def get_football_data_current_matches(team_id, seasons=(2025, 2026), number_of_matches=30):
    all_matches = []
    for season in seasons:
        data = football_data_request(
            f"/teams/{team_id}/matches",
            {"season": season, "status": "FINISHED", "limit": 100},
        )
        if data:
            all_matches.extend(data.get("matches", []))
    all_matches.sort(key=lambda match: match["utcDate"], reverse=True)
    return all_matches[:number_of_matches]

def get_competition_matches(
    competition_code,
    seasons=(2025, 2026)
):

    all_matches = []

    for season in seasons:

        data = football_data_request(
            f"/competitions/{competition_code}/matches",
            {
                "season": season,
                "status": "FINISHED"
            }
        )

        if not data:
            continue

        season_matches = data.get(
            "matches",
            []
        )

        all_matches.extend(
            season_matches
        )

    all_matches.sort(
        key=lambda match: match["utcDate"]
    )

    return all_matches

def normalize_football_data_match(match):
    return {
        "fixture": {"date": match["utcDate"]},
        "teams": {
            "home": {"id": match["homeTeam"]["id"], "name": match["homeTeam"]["name"]},
            "away": {"id": match["awayTeam"]["id"], "name": match["awayTeam"]["name"]},
        },
        "goals": {
            "home": match["score"]["fullTime"]["home"],
            "away": match["score"]["fullTime"]["away"],
        },
    }


def normalize_football_data_matches(matches):
    normalized = []
    for match in matches:
        try:
            normalized.append(normalize_football_data_match(match))
        except (KeyError, TypeError):
            continue
    return normalized


def calculate_team_stats(matches, team_id):
    total_scored = total_conceded = 0
    home_scored = home_conceded = 0
    away_scored = away_conceded = 0
    home_count = away_count = 0
    wins = draws = losses = 0
    scored_by_match = []
    conceded_by_match = []

    for match in sorted(matches, key=lambda m: m.get("fixture", {}).get("date", ""), reverse=True):
        try:
            home_team_id = match["teams"]["home"]["id"]
            away_team_id = match["teams"]["away"]["id"]
            home_goals = match["goals"]["home"]
            away_goals = match["goals"]["away"]
        except (KeyError, TypeError):
            continue

        if home_goals is None or away_goals is None:
            continue

        if home_team_id == team_id:
            scored, conceded = home_goals, away_goals
            home_scored += scored
            home_conceded += conceded
            home_count += 1
        elif away_team_id == team_id:
            scored, conceded = away_goals, home_goals
            away_scored += scored
            away_conceded += conceded
            away_count += 1
        else:
            continue

        total_scored += scored
        total_conceded += conceded
        if scored > conceded:
            wins += 1
        elif scored == conceded:
            draws += 1
        else:
            losses += 1
        scored_by_match.append(scored)
        conceded_by_match.append(conceded)

    match_count = len(scored_by_match)
    if match_count == 0:
        return None

    avg_scored = total_scored / match_count
    avg_conceded = total_conceded / match_count

    def avg(total, count, fallback):
        return fallback if count == 0 else total / count

    recent_scored = scored_by_match[:5]
    recent_conceded = conceded_by_match[:5]

    return {
        "matches": match_count,
        "average_goals_scored": avg_scored,
        "average_goals_conceded": avg_conceded,
        "home_goals_scored": avg(home_scored, home_count, avg_scored),
        "home_goals_conceded": avg(home_conceded, home_count, avg_conceded),
        "away_goals_scored": avg(away_scored, away_count, avg_scored),
        "away_goals_conceded": avg(away_conceded, away_count, avg_conceded),
        "recent_scoring_average": sum(recent_scored) / len(recent_scored),
        "recent_conceding_average": sum(recent_conceded) / len(recent_conceded),
        "wins": wins,
        "draws": draws,
        "losses": losses,
    }


def blend_team_stats(current_stats, historical_stats, current_weight=0.80):
    if current_stats is None:
        return historical_stats
    if historical_stats is None:
        return current_stats
    blended = dict(current_stats)
    keys = [
        "average_goals_scored",
        "average_goals_conceded",
        "home_goals_scored",
        "home_goals_conceded",
        "away_goals_scored",
        "away_goals_conceded",
    ]
    for key in keys:
        blended[key] = (
            current_stats[key] * current_weight
            + historical_stats[key] * (1 - current_weight)
        )
    blended["matches"] = current_stats["matches"] + historical_stats["matches"]
    blended["recent_scoring_average"] = current_stats["recent_scoring_average"]
    blended["recent_conceding_average"] = current_stats["recent_conceding_average"]
    return blended


def form_adjustment(recent_average, overall_average, lower=0.80, upper=1.20):
    if overall_average <= 0:
        return 1.0
    return max(lower, min(upper, recent_average / overall_average))


def calculate_expected_goals(home_stats, away_stats):
    home_expected = (home_stats["home_goals_scored"] + away_stats["away_goals_conceded"]) / 2
    away_expected = (away_stats["away_goals_scored"] + home_stats["home_goals_conceded"]) / 2

    home_attack_form = form_adjustment(
        home_stats["recent_scoring_average"], home_stats["average_goals_scored"]
    )
    away_attack_form = form_adjustment(
        away_stats["recent_scoring_average"], away_stats["average_goals_scored"]
    )
    home_defense_context = form_adjustment(
        away_stats["recent_conceding_average"], away_stats["average_goals_conceded"]
    )
    away_defense_context = form_adjustment(
        home_stats["recent_conceding_average"], home_stats["average_goals_conceded"]
    )

    home_expected *= math.sqrt(home_attack_form * home_defense_context)
    away_expected *= math.sqrt(away_attack_form * away_defense_context)
    home_expected *= 1.05

    return max(0.15, min(4.5, home_expected)), max(0.15, min(4.5, away_expected))


def poisson_probability(goals, expected_goals):
    return math.exp(-expected_goals) * expected_goals ** goals / math.factorial(goals)


def build_score_matrix(home_expected, away_expected, max_goals=10):
    matrix = []
    for home_goals in range(max_goals + 1):
        row = []
        home_p = poisson_probability(home_goals, home_expected)
        for away_goals in range(max_goals + 1):
            away_p = poisson_probability(away_goals, away_expected)
            row.append(home_p * away_p)
        matrix.append(row)
    return matrix


def match_result_probabilities(matrix):
    home_win = draw = away_win = 0
    for home_goals, row in enumerate(matrix):
        for away_goals, probability in enumerate(row):
            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability
    total = home_win + draw + away_win
    return home_win / total, draw / total, away_win / total


def total_goals_probability(matrix, minimum_goals):
    return sum(
        p
        for hg, row in enumerate(matrix)
        for ag, p in enumerate(row)
        if hg + ag >= minimum_goals
    )


def btts_probability(matrix):
    yes = sum(
        p
        for hg, row in enumerate(matrix)
        for ag, p in enumerate(row)
        if hg >= 1 and ag >= 1
    )
    return yes, 1 - yes


def clean_sheet_probabilities(matrix):
    home_clean = sum(matrix[hg][0] for hg in range(len(matrix)))
    away_clean = sum(matrix[0])
    return home_clean, away_clean


def team_scoring_probabilities(matrix):
    values = {"home_1_plus": 0, "home_2_plus": 0, "away_1_plus": 0, "away_2_plus": 0}
    for hg, row in enumerate(matrix):
        for ag, p in enumerate(row):
            if hg >= 1:
                values["home_1_plus"] += p
            if hg >= 2:
                values["home_2_plus"] += p
            if ag >= 1:
                values["away_1_plus"] += p
            if ag >= 2:
                values["away_2_plus"] += p
    return values


def top_scorelines(matrix, limit=5):
    scores = [
        (p, hg, ag)
        for hg, row in enumerate(matrix)
        for ag, p in enumerate(row)
    ]
    scores.sort(reverse=True)
    return scores[:limit]


def display_team_stats(team_name, stats):
    print(f"\n--- {team_name} Statistics ---")
    print(f"Matches represented: {stats['matches']}")
    print(f"Goals scored average: {stats['average_goals_scored']:.2f}")
    print(f"Goals conceded average: {stats['average_goals_conceded']:.2f}")
    print(f"Home scoring average: {stats['home_goals_scored']:.2f}")
    print(f"Home conceding average: {stats['home_goals_conceded']:.2f}")
    print(f"Away scoring average: {stats['away_goals_scored']:.2f}")
    print(f"Away conceding average: {stats['away_goals_conceded']:.2f}")
    print(f"Recent scoring average: {stats['recent_scoring_average']:.2f}")
    print(f"Recent conceding average: {stats['recent_conceding_average']:.2f}")


def display_prediction(home_name, away_name, home_stats, away_stats, home_expected, away_expected, matrix):
    display_team_stats(home_name, home_stats)
    display_team_stats(away_name, away_stats)

    print("\n--- Adjusted Expected Goals ---")
    print(f"{home_name}: {home_expected:.2f}")
    print(f"{away_name}: {away_expected:.2f}")

    print("\n--- Most Likely Scorelines ---")
    for p, hg, ag in top_scorelines(matrix):
        print(f"{home_name} {hg} - {ag} {away_name}: {p:.2%}")

    home_win, draw, away_win = match_result_probabilities(matrix)
    print("\n--- Match Result Probabilities ---")
    print(f"{home_name} win: {home_win:.2%}")
    print(f"Draw: {draw:.2%}")
    print(f"{away_name} win: {away_win:.2%}")

    print("\n--- Double Chance ---")
    print(f"{home_name} or Draw: {home_win + draw:.2%}")
    print(f"{away_name} or Draw: {away_win + draw:.2%}")
    print(f"Either team wins: {home_win + away_win:.2%}")

    print("\n--- Total Goals ---")
    for line, minimum in [(0.5, 1), (1.5, 2), (2.5, 3), (3.5, 4)]:
        over = total_goals_probability(matrix, minimum)
        print(f"Over {line}: {over:.2%}")
        print(f"Under {line}: {1 - over:.2%}")

    btts_yes, btts_no = btts_probability(matrix)
    print("\n--- Both Teams To Score ---")
    print(f"BTTS Yes: {btts_yes:.2%}")
    print(f"BTTS No: {btts_no:.2%}")

    home_clean, away_clean = clean_sheet_probabilities(matrix)
    print("\n--- Clean Sheets ---")
    print(f"{home_name}: {home_clean:.2%}")
    print(f"{away_name}: {away_clean:.2%}")

    scoring = team_scoring_probabilities(matrix)
    print("\n--- Team Goal Ranges ---")
    print(f"{home_name} 1+ goal: {scoring['home_1_plus']:.2%}")
    print(f"{home_name} 2+ goals: {scoring['home_2_plus']:.2%}")
    print(f"{away_name} 1+ goal: {scoring['away_1_plus']:.2%}")
    print(f"{away_name} 2+ goals: {scoring['away_2_plus']:.2%}")

    result_map = {home_name: home_win, "Draw": draw, away_name: away_win}
    predicted_result = max(result_map, key=result_map.get)
    print("\n--- Final Prediction ---")
    print(f"Predicted result: {predicted_result} ({result_map[predicted_result]:.2%})")


def main():
    if not API_FOOTBALL_KEY or not FOOTBALL_DATA_KEY:
        print("Set API_FOOTBALL_KEY and FOOTBALL_DATA_KEY in .env before running live predictions.")
        return
    print("=" * 70)
    print("FOOTBALL PREDICTION MODEL")
    print("=" * 70)

    print("\nMatch Type:")
    print("1. Club")
    print("2. International")

    while True:
        match_type = input("\nChoose match type (1 or 2): ").strip()

        if match_type in ("1", "2"):
            break

        print("Please enter 1 or 2.")

    home_team_name = input("\nEnter the home team: ").strip()
    away_team_name = input("Enter the away team: ").strip()

    if match_type == "1":

        print("\nCompetition Codes:")
        print("PL   = Premier League")
        print("PD   = La Liga")
        print("SA   = Serie A")
        print("BL1  = Bundesliga")
        print("FL1  = Ligue 1")
        print("CL   = Champions League")
        print("DED  = Eredivisie")
        print("PPL  = Primeira Liga")

        competition_code = input(
            "\nEnter Football-Data competition code: ").strip().upper()

    else:

        competition_code = None

        print("\nInternational Match Type:")
        print("1. Friendly")
        print("2. World Cup")
        print("3. World Cup Qualifier")
        print("4. European Championship")
        print("5. Nations League")
        print("6. Other")
        international_type = input("\nChoose international competition: ").strip()
        print("\nInternational data collection is not implemented in this release.")
        print("Use Club mode for now; this option will not generate a misleading prediction.")
        return
        
    current_seasons = (2025, 2026)
    historical_seasons = (2022, 2023, 2024)

    print("\nSearching API-Football for home team...")
    home_api_team = find_api_football_team(home_team_name)
    if home_api_team is None:
        print("Could not find home team in API-Football.")
        return

    print("\nSearching API-Football for away team...")
    away_api_team = find_api_football_team(away_team_name)
    if away_api_team is None:
        print("Could not find away team in API-Football.")
        return

    print("\nSearching Football-Data for home team...")
    home_current_team = find_football_data_team(home_team_name, competition_code)
    if home_current_team is None:
        print("Could not find home team in Football-Data.")
        return

    print("\nSearching Football-Data for away team...")
    away_current_team = find_football_data_team(away_team_name, competition_code)
    if away_current_team is None:
        print("Could not find away team in Football-Data.")
        return

    print("\nGetting historical home-team matches...")
    home_historical_matches = get_api_football_historical_matches(
        home_api_team["id"], historical_seasons, 20
    )
    print("Getting historical away-team matches...")
    away_historical_matches = get_api_football_historical_matches(
        away_api_team["id"], historical_seasons, 20
    )

    print("\nGetting 2025/2026 home-team matches...")
    home_current_raw = get_football_data_current_matches(
        home_current_team["id"], current_seasons, 30
    )
    print("Getting 2025/2026 away-team matches...")
    away_current_raw = get_football_data_current_matches(
        away_current_team["id"], current_seasons, 30
    )

    home_current_matches = normalize_football_data_matches(home_current_raw)
    away_current_matches = normalize_football_data_matches(away_current_raw)

    

    print(
        "\nGetting competition-wide matches "
        "for opponent-strength analysis..."
    )

    competition_matches_raw = get_competition_matches(
        competition_code,
        current_seasons
    )

    competition_matches = (
        normalize_football_data_matches(
            competition_matches_raw
        )
    )

    if not competition_matches:

        print(
            "Could not retrieve enough "
            "competition data for Phase 3."
        )

        return

    # Phase 3: Elo and opponent-adjusted form, using ONLY Football-Data IDs.
    phase3 = run_opponent_strength_model(
        competition_matches,
        home_current_matches,
        away_current_matches,
        home_current_team["id"],
        away_current_team["id"],
    )
    home_current_stats = phase3["home_stats"]
    away_current_stats = phase3["away_stats"]
    comparison = phase3["comparison"]

    if home_current_stats is None or away_current_stats is None:
        print("Insufficient recent results to estimate one or both teams.")
        return

    # API-Football historical IDs are not interchangeable with Football-Data IDs.
    home_historical_stats = calculate_team_stats(home_historical_matches, home_api_team["id"])
    away_historical_stats = calculate_team_stats(away_historical_matches, away_api_team["id"])

    home_stats = blend_team_stats(home_current_stats, home_historical_stats)
    away_stats = blend_team_stats(away_current_stats, away_historical_stats)

    print("\n--- Opponent strength diagnostics ---")
    for name, stats in ((home_current_team["name"], home_current_stats),
                        (away_current_team["name"], away_current_stats)):
        print(f"{name}: Elo {stats['elo_rating']:.1f}, "
              f"avg opponent Elo {stats['average_opponent_rating']:.1f}, "
              f"schedule multiplier {stats['schedule_multiplier']:.3f}")
    print(f"Elo difference (home - away): {comparison['rating_difference']:+.1f}")

    home_expected, away_expected = calculate_expected_goals(home_stats, away_stats)

    # Match context is computed from competition results before the prediction date.
    from datetime import datetime, timezone
    kickoff_text = input("\nMatch kickoff (YYYY-MM-DD HH:MM UTC, Enter for now): ").strip()
    if kickoff_text:
        try:
            kickoff = datetime.strptime(kickoff_text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            print("Invalid kickoff format. Use YYYY-MM-DD HH:MM in UTC.")
            return
    else:
        kickoff = datetime.now(timezone.utc)
    # Prevent using competition results after the specified kickoff.
    context_history = [m for m in competition_matches
        if m["fixture"]["date"] < kickoff.isoformat().replace("+00:00", "Z")]
    home_expected, away_expected, home_context, away_context = apply_match_context(
        home_expected,
        away_expected,
        context_history,
        home_current_team["id"],
        away_current_team["id"],
        kickoff
    )
    print("\n--- Fixture context (prior fixtures only) ---")
    for name, ctx in ((home_current_team["name"], home_context),
                      (away_current_team["name"], away_context)):
        print(f"{name}: rest={ctx['rest_days']} days, "
              f"games in last 7 days={ctx['matches_last_7']}, "
              f"attack factor={ctx['factor']:.3f}")

# ---------------------------------------------------------
# SQUAD AVAILABILITY ANALYSIS
# ---------------------------------------------------------
    display_squad_report(
        api_football_request,
        home_api_team["id"],
        away_api_team["id"],
        home_current_team["name"],
        away_current_team["name"],
        kickoff
    )
    # Squad factors default to neutral until verified availability is provided.
    home_expected, away_expected = apply_squad_adjustments(home_expected, away_expected)
    matrix = build_score_matrix(home_expected, away_expected, max_goals=10)
    # Heuristic low-score dependence adjustment; rho is not fitted yet.
    matrix = dixon_coles_matrix(matrix, home_expected, away_expected)

    display_prediction(
        home_current_team["name"],
        away_current_team["name"],
        home_stats,
        away_stats,
        home_expected,
        away_expected,
        matrix,
    )

    print("=" * 70)


if __name__ == "__main__":
    main()