import unittest
from datetime import datetime, timezone
from match_context import team_context, apply_match_context
from squad_model import apply_squad_adjustments
from draw_model import dixon_coles_matrix
from main import build_score_matrix, match_result_probabilities

def m(day):
    return {"fixture":{"date":f"2026-10-{day:02d}T12:00:00Z"},
            "teams":{"home":{"id":1},"away":{"id":2}},
            "goals":{"home":1,"away":0}}

class ContextTests(unittest.TestCase):
    def test_rest(self):
        c = team_context([m(18), m(21), m(23)], 1, "2026-10-24T12:00:00Z")
        self.assertEqual(c["matches_last_7"], 3)
        self.assertLess(c["factor"], 1)
    def test_future_does_not_leak(self):
        a = team_context([m(18)], 1, "2026-10-20T12:00:00Z")
        b = team_context([m(18), m(23)], 1, "2026-10-20T12:00:00Z")
        self.assertEqual(a, b)
    def test_squad_neutral(self):
        self.assertEqual(apply_squad_adjustments(1.5, 1.2), (1.5, 1.2))
    def test_dc_normalizes(self):
        mat = dixon_coles_matrix(build_score_matrix(1.5, 1.2), 1.5, 1.2)
        self.assertAlmostEqual(sum(map(sum, mat)), 1, places=8)
        self.assertGreater(match_result_probabilities(mat)[1], 0)

if __name__ == "__main__":
    unittest.main()
