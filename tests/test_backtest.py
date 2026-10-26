import unittest
from backtest import evaluate, metrics


def fixture(day, h, a, hg, ag):
    return {"fixture": {"date": f"2026-01-{day:02d}T12:00:00Z"},
            "teams": {"home": {"id": h, "name": str(h)}, "away": {"id": a, "name": str(a)}},
            "goals": {"home": hg, "away": ag}}


class BacktestTests(unittest.TestCase):
    def test_no_future_data(self):
        base = [fixture(i, 1 if i % 2 else 2, 2 if i % 2 else 1, i % 3, (i+1) % 3)
                for i in range(1, 12)]
        original, _, _ = evaluate(base, min_team_matches=3)
        extra = fixture(12, 1, 2, 20, 0)
        extended, _, _ = evaluate(base + [extra], min_team_matches=3)
        self.assertEqual(original, extended[:-1])

    def test_same_kickoff_not_leaked(self):
        base = [fixture(i, 1, 2, 1, 0) for i in range(1, 5)]
        base.append(fixture(5, 1, 2, 0, 1))
        base.append(fixture(5, 2, 3, 2, 0))
        rows, _, _ = evaluate(base, min_team_matches=3)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["history_matches"], 4)

    def test_metrics(self):
        rows = [{"predicted": "H", "actual": "H", "p_home": .7, "p_draw": .2, "p_away": .1}]
        result = metrics(rows)
        self.assertEqual(result["accuracy"], 1.0)
        self.assertAlmostEqual(result["brier_3class"], .14)

if __name__ == "__main__":
    unittest.main()