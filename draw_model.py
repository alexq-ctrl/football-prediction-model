"""Dixon-Coles low-score dependence correction for independent Poisson matrices."""
def dixon_coles_matrix(matrix, home_xg, away_xg, rho=-0.06):
    if not -0.15 <= rho <= 0.15:
        raise ValueError("rho must be between -0.15 and 0.15")
    result = [row[:] for row in matrix]
    corrections = {
        (0, 0): 1 - home_xg * away_xg * rho,
        (0, 1): 1 + home_xg * rho,
        (1, 0): 1 + away_xg * rho,
        (1, 1): 1 - rho,
    }
    for (h, a), factor in corrections.items():
        if h < len(result) and a < len(result[h]):
            result[h][a] *= max(0.0, factor)
    total = sum(sum(row) for row in result)
    return [[p / total for p in row] for row in result]
