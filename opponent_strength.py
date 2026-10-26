import math
from datetime import datetime


# ============================================================
# PHASE 3
# OPPONENT STRENGTH / STRENGTH OF SCHEDULE
# ============================================================


# ============================================================
# 1. DATE HELPERS
# ============================================================

def parse_match_date(date_string):
    """
    Converts API date strings into Python datetime objects.

    Works with dates like:
    2026-09-14T01:00:00Z
    """

    if not date_string:
        return datetime.min.replace(tzinfo=__import__("datetime").timezone.utc)

    try:
        return datetime.fromisoformat(
            date_string.replace("Z", "+00:00")
        )

    except ValueError:
        return datetime.min.replace(tzinfo=__import__("datetime").timezone.utc)


# ============================================================
# 2. SORT MATCHES
# ============================================================

def sort_matches_oldest_first(matches):

    return sorted(
        matches,
        key=lambda match: parse_match_date(
            match["fixture"]["date"]
        )
    )


def sort_matches_newest_first(matches):

    return sorted(
        matches,
        key=lambda match: parse_match_date(
            match["fixture"]["date"]
        ),
        reverse=True
    )


# ============================================================
# 3. ELO EXPECTED RESULT
# ============================================================

def elo_expected_score(
    rating_a,
    rating_b
):

    return (
        1
        /
        (
            1
            +
            10 ** (
                (rating_b - rating_a)
                / 400
            )
        )
    )


# ============================================================
# 4. ACTUAL MATCH RESULT
# ============================================================

def actual_result(
    goals_for,
    goals_against
):

    if goals_for > goals_against:
        return 1.0

    if goals_for == goals_against:
        return 0.5

    return 0.0


# ============================================================
# 5. GOAL DIFFERENCE MULTIPLIER
# ============================================================

def goal_difference_multiplier(
    goals_for,
    goals_against
):

    difference = abs(
        goals_for
        - goals_against
    )

    if difference <= 1:
        return 1.0

    if difference == 2:
        return 1.25

    if difference == 3:
        return 1.45

    return 1.60


# ============================================================
# 6. BUILD ELO RATINGS
# ============================================================

def build_elo_ratings(
    matches,
    starting_rating=1500,
    k_factor=24,
    home_advantage=60
):

    ratings = {}

    sorted_matches = sort_matches_oldest_first(
        matches
    )

    for match in sorted_matches:

        try:

            home_id = (
                match["teams"]
                ["home"]
                ["id"]
            )

            away_id = (
                match["teams"]
                ["away"]
                ["id"]
            )

            home_goals = (
                match["goals"]["home"]
            )

            away_goals = (
                match["goals"]["away"]
            )

        except (
            KeyError,
            TypeError
        ):

            continue


        if (
            home_goals is None
            or away_goals is None
        ):

            continue


        if home_id not in ratings:
            ratings[home_id] = (
                starting_rating
            )

        if away_id not in ratings:
            ratings[away_id] = (
                starting_rating
            )


        home_rating = ratings[home_id]

        away_rating = ratings[away_id]


        # Home advantage is used only
        # when calculating expected result.

        adjusted_home_rating = (
            home_rating
            + home_advantage
        )


        expected_home = (
            elo_expected_score(
                adjusted_home_rating,
                away_rating
            )
        )

        expected_away = (
            1 - expected_home
        )


        actual_home = actual_result(
            home_goals,
            away_goals
        )

        actual_away = (
            1 - actual_home
        )


        margin_multiplier = (
            goal_difference_multiplier(
                home_goals,
                away_goals
            )
        )


        home_change = (
            k_factor
            * margin_multiplier
            * (
                actual_home
                - expected_home
            )
        )

        away_change = (
            k_factor
            * margin_multiplier
            * (
                actual_away
                - expected_away
            )
        )


        ratings[home_id] = (
            home_rating
            + home_change
        )

        ratings[away_id] = (
            away_rating
            + away_change
        )


    return ratings


# ============================================================
# 7. GET TEAM RATING
# ============================================================

def get_team_rating(
    team_id,
    ratings,
    default_rating=1500
):

    return ratings.get(
        team_id,
        default_rating
    )


# ============================================================
# 8. OPPONENT STRENGTH MULTIPLIER
# ============================================================

def opponent_strength_multiplier(
    opponent_rating,
    average_rating=1500
):

    difference = (
        opponent_rating
        - average_rating
    )


    multiplier = (
        1
        + difference / 1000
    )


    # Prevent extreme values.

    multiplier = max(
        0.70,
        multiplier
    )

    multiplier = min(
        1.30,
        multiplier
    )


    return multiplier


# ============================================================
# 9. RECENCY WEIGHT
# ============================================================

def recency_weight(
    match_number,
    half_life=10
):

    return (
        0.5
        **
        (
            match_number
            / half_life
        )
    )


# ============================================================
# 10. FIND OPPONENT
# ============================================================

def get_opponent_id(
    match,
    team_id
):

    home_id = (
        match["teams"]
        ["home"]
        ["id"]
    )

    away_id = (
        match["teams"]
        ["away"]
        ["id"]
    )


    if home_id == team_id:
        return away_id

    if away_id == team_id:
        return home_id

    return None


# ============================================================
# 11. TEAM GOALS IN MATCH
# ============================================================

def get_team_match_result(
    match,
    team_id
):

    home_id = (
        match["teams"]
        ["home"]
        ["id"]
    )

    away_id = (
        match["teams"]
        ["away"]
        ["id"]
    )

    home_goals = (
        match["goals"]["home"]
    )

    away_goals = (
        match["goals"]["away"]
    )


    if (
        home_goals is None
        or away_goals is None
    ):

        return None


    if home_id == team_id:

        return {
            "home": True,
            "scored": home_goals,
            "conceded": away_goals
        }


    if away_id == team_id:

        return {
            "home": False,
            "scored": away_goals,
            "conceded": home_goals
        }


    return None


# ============================================================
# 12. CALCULATE STRENGTH OF SCHEDULE
# ============================================================

def calculate_schedule_strength(
    matches,
    team_id,
    ratings
):

    opponent_ratings = []


    for match in matches:

        opponent_id = get_opponent_id(
            match,
            team_id
        )

        if opponent_id is None:
            continue


        opponent_rating = (
            get_team_rating(
                opponent_id,
                ratings
            )
        )


        opponent_ratings.append(
            opponent_rating
        )


    if not opponent_ratings:

        return {
            "average_opponent_rating": 1500,
            "schedule_multiplier": 1.0
        }


    average_opponent_rating = (
        sum(opponent_ratings)
        /
        len(opponent_ratings)
    )


    schedule_multiplier = (
        opponent_strength_multiplier(
            average_opponent_rating
        )
    )


    return {
        "average_opponent_rating":
            average_opponent_rating,

        "schedule_multiplier":
            schedule_multiplier
    }


# ============================================================
# 13. OPPONENT-ADJUSTED TEAM STATS
# ============================================================

def calculate_opponent_adjusted_stats(
    matches,
    team_id,
    ratings,
    half_life=10
):

    matches = sort_matches_newest_first(
        matches
    )


    total_scored = 0
    total_conceded = 0
    total_weight = 0


    home_scored = 0
    home_conceded = 0
    home_weight = 0


    away_scored = 0
    away_conceded = 0
    away_weight = 0


    wins = 0
    draws = 0
    losses = 0


    recent_scored = []
    recent_conceded = []


    for index, match in enumerate(
        matches
    ):

        result = get_team_match_result(
            match,
            team_id
        )

        if result is None:
            continue


        opponent_id = get_opponent_id(
            match,
            team_id
        )


        opponent_rating = (
            get_team_rating(
                opponent_id,
                ratings
            )
        )


        strength_weight = (
            opponent_strength_multiplier(
                opponent_rating
            )
        )


        time_weight = recency_weight(
            index,
            half_life
        )


        final_weight = time_weight


        scored = result["scored"]

        conceded = result["conceded"]


        # ------------------------------------
        # Weighted overall stats
        # ------------------------------------

        total_scored += (
            scored
            * strength_weight
            * final_weight
        )

        total_conceded += (
            conceded
            / strength_weight
            * final_weight
        )

        total_weight += (
            final_weight
        )


        # ------------------------------------
        # Home / Away splits
        # ------------------------------------

        if result["home"]:

            home_scored += (
                scored
                * final_weight
            )

            home_conceded += (
                conceded
                * final_weight
            )

            home_weight += (
                final_weight
            )


        else:

            away_scored += (
                scored
                * final_weight
            )

            away_conceded += (
                conceded
                * final_weight
            )

            away_weight += (
                final_weight
            )


        # ------------------------------------
        # Win / Draw / Loss
        # ------------------------------------

        if scored > conceded:
            wins += 1

        elif scored == conceded:
            draws += 1

        else:
            losses += 1


        # ------------------------------------
        # Recent form
        # ------------------------------------

        if len(recent_scored) < 5:

            recent_scored.append(
                scored
            )

            recent_conceded.append(
                conceded
            )


    if total_weight == 0:

        return None


    overall_scored = (
        total_scored
        / total_weight
    )

    overall_conceded = (
        total_conceded
        / total_weight
    )


    if home_weight > 0:

        home_goals_scored = (
            home_scored
            / home_weight
        )

        home_goals_conceded = (
            home_conceded
            / home_weight
        )

    else:

        home_goals_scored = (
            overall_scored
        )

        home_goals_conceded = (
            overall_conceded
        )


    if away_weight > 0:

        away_goals_scored = (
            away_scored
            / away_weight
        )

        away_goals_conceded = (
            away_conceded
            / away_weight
        )

    else:

        away_goals_scored = (
            overall_scored
        )

        away_goals_conceded = (
            overall_conceded
        )


    recent_scoring_average = (
        sum(recent_scored)
        / len(recent_scored)
    )


    recent_conceding_average = (
        sum(recent_conceded)
        / len(recent_conceded)
    )


    schedule = (
        calculate_schedule_strength(
            matches,
            team_id,
            ratings
        )
    )


    return {

        "matches":
            wins
            + draws
            + losses,

        "average_goals_scored":
            overall_scored,

        "average_goals_conceded":
            overall_conceded,

        "home_goals_scored":
            home_goals_scored,

        "home_goals_conceded":
            home_goals_conceded,

        "away_goals_scored":
            away_goals_scored,

        "away_goals_conceded":
            away_goals_conceded,

        "recent_scoring_average":
            recent_scoring_average,

        "recent_conceding_average":
            recent_conceding_average,

        "wins":
            wins,

        "draws":
            draws,

        "losses":
            losses,

        "elo_rating":
            get_team_rating(
                team_id,
                ratings
            ),

        "average_opponent_rating":
            schedule[
                "average_opponent_rating"
            ],

        "schedule_multiplier":
            schedule[
                "schedule_multiplier"
            ]
    }


# ============================================================
# 14. COMPARE TWO TEAMS
# ============================================================

def compare_team_strength(
    home_team_id,
    away_team_id,
    ratings
):

    home_rating = get_team_rating(
        home_team_id,
        ratings
    )

    away_rating = get_team_rating(
        away_team_id,
        ratings
    )


    home_expected = (
        elo_expected_score(
            home_rating + 60,
            away_rating
        )
    )


    away_expected = (
        1 - home_expected
    )


    return {

        "home_rating":
            home_rating,

        "away_rating":
            away_rating,

        "home_elo_expected_score":
            home_expected,

        "away_elo_expected_score":
            away_expected,

        "rating_difference":
            home_rating
            - away_rating
    }


# ============================================================
# 15. BUILD MATCH POOL
# ============================================================

def combine_match_pools(
    *match_lists
):

    combined = []


    for match_list in match_lists:

        if not match_list:
            continue

        combined.extend(
            match_list
        )


    # Remove duplicate fixtures
    # when possible.

    unique_matches = {}

    for match in combined:

        try:

            date = (
                match["fixture"]["date"]
            )

            home_id = (
                match["teams"]
                ["home"]
                ["id"]
            )

            away_id = (
                match["teams"]
                ["away"]
                ["id"]
            )


            key = (
                date,
                home_id,
                away_id
            )


            unique_matches[key] = (
                match
            )


        except (
            KeyError,
            TypeError
        ):

            continue


    return list(
        unique_matches.values()
    )


# ============================================================
# 16. PHASE 3 MASTER FUNCTION
# ============================================================

def run_opponent_strength_model(
    all_matches,
    home_team_matches,
    away_team_matches,
    home_team_id,
    away_team_id
):

    ratings = build_elo_ratings(
        all_matches
    )


    home_stats = (
        calculate_opponent_adjusted_stats(
            home_team_matches,
            home_team_id,
            ratings
        )
    )


    away_stats = (
        calculate_opponent_adjusted_stats(
            away_team_matches,
            away_team_id,
            ratings
        )
    )


    comparison = (
        compare_team_strength(
            home_team_id,
            away_team_id,
            ratings
        )
    )


    return {

        "ratings":
            ratings,

        "home_stats":
            home_stats,

        "away_stats":
            away_stats,

        "comparison":
            comparison
    }

