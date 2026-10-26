# Football Match Probability Model

An independent Python data science project estimating soccer match outcomes using historical results, opponent-adjusted form, Elo ratings, and a Poisson score model.

## Current features
- Football-Data.org current/recent club fixtures and competition-wide results
- API-Football historical team results (if available under your subscription)
- Elo ratings, schedule difficulty, recency-weighted attack/defense statistics
- Historical/current blending and Poisson goal model
- Home/draw/away, scorelines, over/under totals, BTTS, double chance, clean sheets

## Limitations
- **Club mode only currently.** International is a visible placeholder that exits safely.
- Competition availability and historical season access depend on API plans.
- Squad availability, injuries, manager effects, and rest/travel adjustments are **not yet implemented**.
- Elo and blending parameters are heuristic and **not calibrated**.
- The model is not yet historically backtested for predictive performance.
- Football-Data and API-Football IDs are kept separate.
- Treat predictions as exploratory probabilities, not betting guarantees.

## Setup
1. Install Python 3.10+.
2. `python3 -m pip install -r requirements.txt`
3. In the same terminal session, set `API_FOOTBALL_KEY` and `FOOTBALL_DATA_KEY` as environment variables. Never commit your keys.
4. `python3 main.py`
5. Choose **1 (Club)** and an accessible competition code.

Example on macOS:
```bash
export API_FOOTBALL_KEY="your_key"
export FOOTBALL_DATA_KEY="your_key"
python3 main.py
```

## Verify locally
```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile main.py opponent_strength.py
```

Tests use synthetic match results and do not call live APIs.

## Next development steps
- Add international fixture data with reliable coverage checks.
- Add optional squad and match-context features with verified sources.
- Build walk-forward backtests (only matches available before each prediction), then calibrate probabilities.
- Add a data export for Excel/SQL analysis.

## Method
Each competition's completed results are used to construct Elo ratings. Team performances are weighted by opponent quality and recency. Adjusted current statistics are blended with available historical averages to estimate each team's expected goals. An independent Poisson model produces score probabilities and derived markets.

**Caution:** current Elo calculations use all completed results returned by the API; for historical evaluation, the match pool must be cut off before each target match to prevent future-data leakage.

## Walk-forward backtesting

Run from the project folder:

```bash
python3 backtest.py --competition PL --seasons 2025 2026 --output backtest_results.csv
```

Or use an exported Football-Data API JSON file offline:

```bash
python3 backtest.py --input-json matches.json --output backtest_results.csv
```

The script uses only **completed matches before each kickoff** to calculate Elo and team form. Same-time matches cannot leak into one another. It requires eight prior matches per team by default, and uses the latest 30 per team. It outputs a match-by-match CSV and aggregate top-pick accuracy, 3-class multiclass Brier score (sum of squared errors; range 0–2), and log loss (lower is better).

**Important:** This is a backtest of the *current-data Phase 3 + Poisson* model, not the full live model with API-Football historical blending. It uses the final Elo ratings as of each prediction time for opponent-adjusted prior performances; it does not replay ratings as of each individual earlier match. Its parameters were not fitted or calibrated. API season access depends on your plan. Do not describe this as validated betting profitability.
\n## New experimental modules\n- `match_context.py`: rest days and congestion, computed strictly from earlier fixtures. Live run uses current time because it does not yet ask for a match kickoff date.\n- `squad_model.py`: verified/manual squad factors; defaults to neutral (no live injury feed).\n- `draw_model.py`: Dixon-Coles low-score adjustment with heuristic rho=-0.06 (not fitted).\n- `backtest.py` now includes context and draw correction; rerun to measure changes. Do not compare scores as identical model versions.\n