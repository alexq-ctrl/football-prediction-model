import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opponent_strength import build_elo_ratings, run_opponent_strength_model

def match(date, home, away, hg, ag):
    return {"fixture": {"date": date},
            "teams": {"home": {"id": home}, "away": {"id": away}},
            "goals": {"home": hg, "away": ag}}

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.matches = [
            match("2026-01-01T12:00:00Z", 1, 2, 2, 0),
            match("2026-01-02T12:00:00Z", 3, 1, 1, 2),
            match("2026-01-03T12:00:00Z", 2, 3, 1, 1),
            match("2026-01-04T12:00:00Z", 2, 1, 0, 1),
        ]
    def test_winner_gains_elo(self):
        ratings = build_elo_ratings(self.matches)
        self.assertGreater(ratings[1], ratings[2])
    def test_phase3_returns_stats(self):
        result = run_opponent_strength_model(
            self.matches, self.matches, self.matches, 1, 2
        )
        self.assertEqual(result["home_stats"]["matches"], 3)
        self.assertEqual(result["away_stats"]["matches"], 3)
        self.assertGreater(result["home_stats"]["elo_rating"], 1500)
    def test_strength_weight_changes_attack(self):
        result = run_opponent_strength_model(
            self.matches, self.matches, self.matches, 1, 2
        )
        self.assertGreater(result["home_stats"]["average_goals_scored"], 0)

if __name__ == "__main__":
    unittest.main()
