"""Evaluate backtest predictions against simple, leakage-free baselines.

Usage: python3 evaluate_baselines.py --input backtest_results.csv
Uses only Python's standard library; no API calls.
"""
import argparse
import csv
import math
from collections import Counter
from pathlib import Path

OUTCOMES = ('H', 'D', 'A')


def score(rows, probabilities):
    n = len(rows)
    if not n:
        raise ValueError('No matches to evaluate')
    correct = brier = logloss = 0.0
    for row, p in zip(rows, probabilities):
        actual = row['actual']
        correct += max(OUTCOMES, key=lambda k: p[k]) == actual
        brier += sum((p[k] - float(k == actual)) ** 2 for k in OUTCOMES)
        logloss -= math.log(max(p[actual], 1e-15))
    return correct / n, brier / n, logloss / n


def analyze(path):
    with path.open(newline='', encoding='utf-8-sig') as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError('CSV contains no predictions')
    for row in rows:
        if row.get('actual') not in OUTCOMES:
            raise ValueError('CSV must contain actual values H, D, A')
        for col in ('p_home', 'p_draw', 'p_away'):
            if col not in row:
                raise ValueError(f'Missing required column: {col}')
    # Sort so expanding baseline can only learn from earlier completed matches.
    # All matches sharing a kickoff are scored before the counts are updated.
    if 'date_utc' not in rows[0]:
        raise ValueError('Missing date_utc; cannot build chronological baseline')
    rows.sort(key=lambda row: row['date_utc'])
    model = []
    for row in rows:
        p = dict(zip(OUTCOMES, (float(row['p_home']), float(row['p_draw']), float(row['p_away']))))
        if any(not math.isfinite(x) or x < 0 for x in p.values()) or not 0.999 <= sum(p.values()) <= 1.001:
            raise ValueError('Invalid model probabilities in CSV')
        model.append(p)

    uniform = [{k: 1/3 for k in OUTCOMES} for _ in rows]
    # Fixed home-heavy benchmark; avoids zero probabilities and uses no fitted parameters.
    home_bias = [{'H': 0.50, 'D': 0.25, 'A': 0.25} for _ in rows]
    # Expanding empirical frequency baseline; 1 pseudo-count per outcome.
    # This baseline is trained on EVALUATED games only; skipped games are not available here.
    prior = []
    counts = Counter()
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and rows[j]['date_utc'] == rows[i]['date_utc']:
            j += 1
        total = sum(counts.values())
        p = {k: (counts[k] + 1) / (total + 3) for k in OUTCOMES}
        prior.extend([p.copy() for _ in range(j - i)])
        counts.update(row['actual'] for row in rows[i:j])
        i = j

    print(f'\nMatches evaluated: {len(rows)}')
    print('Baseline comparison (lower Brier and log loss are better):')
    print(f'{"Method":<29} {"Accuracy":>10} {"Brier":>10} {"Log loss":>10}')
    for name, preds in [('Football model', model), ('Uniform 1/3 each', uniform),
                        ('Fixed home bias 50/25/25', home_bias),
                        ('Expanding outcome frequencies', prior)]:
        accuracy, brier, loss = score(rows, preds)
        print(f'{name:<29} {accuracy:>9.2%} {brier:>10.4f} {loss:>10.4f}')

    print('\nActual outcome frequencies:')
    actual = Counter(row['actual'] for row in rows)
    for k, label in [('H', 'Home wins'), ('D', 'Draws'), ('A', 'Away wins')]:
        print(f'  {label}: {actual[k]}/{len(rows)} ({actual[k]/len(rows):.1%})')

    print('\nCalibration by predicted probability (all three outcome classes pooled):')
    print(f'{"Probability range":<20} {"Count":>7} {"Mean predicted":>16} {"Actual rate":>14}')
    for lower in (0, .2, .4, .6, .8):
        bucket = [(p[k], float(row['actual'] == k)) for row, p in zip(rows, model)
                  for k in OUTCOMES if lower <= p[k] < lower + .2 or (lower == .8 and p[k] == 1)]
        if bucket:
            print(f'{lower:.0%}–{lower+.2:.0%}{"":<14} {len(bucket):>7} '
                  f'{sum(p for p, _ in bucket)/len(bucket):>15.1%} '
                  f'{sum(y for _, y in bucket)/len(bucket):>13.1%}')
    print('\nNote: These comparisons use the same evaluated CSV rows. The expanding baseline')
    print('uses only earlier evaluated results; it does not use skipped fixtures.')
    print('This is descriptive evaluation, not evidence of profitable betting.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('backtest_results.csv'))
    args = parser.parse_args()
    analyze(args.input)
