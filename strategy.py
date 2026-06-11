import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize

MAX_GOALS = 10


# ─── Utilidades ───────────────────────────────────────────────────────────────

def build_matrix(lam_h, lam_a):
    i = np.arange(MAX_GOALS + 1)
    return np.outer(poisson.pmf(i, lam_h), poisson.pmf(i, lam_a))


def apply_dixon_coles(matrix, lam_h, lam_a, rho=-0.13):
    m = matrix.copy()
    m[0, 0] *= 1 - lam_h * lam_a * rho
    m[1, 0] *= 1 + lam_a * rho
    m[0, 1] *= 1 + lam_h * rho
    m[1, 1] *= 1 - rho
    return m / m.sum()


def matrix_1x2(matrix):
    return (np.sum(np.tril(matrix, -1)),
            np.sum(np.diag(matrix)),
            np.sum(np.triu(matrix, 1)))


def matrix_ou(matrix, line):
    i = np.arange(MAX_GOALS + 1)
    mask = (i[:, None] + i[None, :]) > line
    return float(np.sum(matrix[mask]))


def matrix_ah(matrix, line):
    """P(home gana con handicap line aplicado, ej line=-1.25 → home gana por 2+)."""
    i = np.arange(MAX_GOALS + 1)
    diff = i[:, None] - i[None, :]        # home_goals - away_goals
    mask = diff + line > 0
    return float(np.sum(matrix[mask]))


def best_score_max_ev(matrix, puntos_exacto=6, puntos_resultado=3):
    i = np.arange(MAX_GOALS + 1)
    result_matrix = np.where(i[:, None] > i[None, :], 0,
                    np.where(i[:, None] == i[None, :], 1, 2))
    ev_matrix = np.zeros_like(matrix)
    for res_val in [0, 1, 2]:
        mask = result_matrix == res_val
        p_result_total = float(np.sum(matrix[mask]))
        idxs = np.argwhere(mask)
        for ii, jj in idxs:
            p_exact = matrix[ii, jj]
            p_result = p_result_total - p_exact
            ev_matrix[ii, jj] = (p_exact * puntos_exacto +
                                  p_result * puntos_resultado)
    idx = np.unravel_index(np.argmax(ev_matrix), ev_matrix.shape)
    return int(idx[0]), int(idx[1])


def get_result(h, a):
    if h > a: return "home"
    if h == a: return "draw"
    return "away"


# ─── Inferencia de lambdas ────────────────────────────────────────────────────

def infer_lambdas_base(moneyline, total_main, spread_main):
    """
    Estrategia base: 1X2 + O/U principal + AH principal.
    Equivalente a S3 del modelo histórico.
    """
    f1x2 = moneyline
    fou_line = total_main["line"]
    fou_over = total_main["over"]
    ah_line = spread_main["line"] if spread_main else None

    def loss(params):
        lh, la = params
        if lh <= 0 or la <= 0:
            return 1e6
        mat = build_matrix(lh, la)
        ph, pd_, pa = matrix_1x2(mat)
        po = matrix_ou(mat, fou_line)
        err = ((ph - f1x2["home"])**2 +
               (pd_ - f1x2["draw"])**2 +
               (pa - f1x2["away"])**2 +
               (po - fou_over)**2)
        if ah_line is not None:
            p_ah = matrix_ah(mat, ah_line)
            err += 0.3 * (p_ah - 0.5)**2
        return err

    lh0, la0 = _initial_guess(f1x2, total_main)
    res = minimize(loss, x0=[lh0, la0], method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-6, "maxiter": 2000})
    return max(res.x[0], 0.1), max(res.x[1], 0.1)


def infer_lambdas_rich(moneyline, total_main, totals_alt, spread_main, spreads_alt, tt_home, tt_away):
    """
    Estrategia enriquecida con pesos por calidad de señal:
      - 1X2:         peso 1.0
      - O/U main:    peso 1.0
      - AH main:     peso 1.0
      - O/U alt:     peso 0.3 por línea (valor marginal decreciente)
      - AH alt:      peso 0.3 por línea (valor marginal decreciente)
      - TT home/away: peso 1.0 (bajado de 2.0, margen más alto)
    """
    f1x2 = moneyline

    def loss(params):
        lh, la = params
        if lh <= 0 or la <= 0:
            return 1e6
        mat = build_matrix(lh, la)
        ph, pd_, pa = matrix_1x2(mat)

        err = ((ph - f1x2["home"])**2 +
               (pd_ - f1x2["draw"])**2 +
               (pa - f1x2["away"])**2)

        # O/U main — peso 1.0
        if total_main:
            po = matrix_ou(mat, total_main["line"])
            err += (po - total_main["over"])**2

        # O/U alt — peso 0.3 por línea
        for t in totals_alt:
            po = matrix_ou(mat, t["line"])
            err += 0.3 * (po - t["over"])**2

        # AH main — peso 1.0
        if spread_main:
            p_ah = matrix_ah(mat, spread_main["line"])
            err += (p_ah - 0.5)**2

        # AH alt — peso 0.3 por línea
        for s in spreads_alt:
            p_ah = matrix_ah(mat, s["line"])
            err += 0.3 * (p_ah - s["home"])**2

        # Team totals — peso 1.0 (único mercado que separa λH y λA)
        if tt_home:
            p_home_over = float(1 - poisson.cdf(tt_home["line"], lh))
            err += 1.0 * (p_home_over - tt_home["over"])**2

        if tt_away:
            p_away_over = float(1 - poisson.cdf(tt_away["line"], la))
            err += 1.0 * (p_away_over - tt_away["over"])**2

        return err

    # Punto inicial: TT dan buena aproximación directa de cada lambda
    lh0 = _lambda_from_tt(tt_home) if tt_home else None
    la0 = _lambda_from_tt(tt_away) if tt_away else None

    # Fallback si no hay TT
    if lh0 is None or la0 is None:
        fallback = total_main or _pick_main_total(totals_alt)
        lh0, la0 = _initial_guess(f1x2, fallback)

    res = minimize(loss, x0=[lh0, la0], method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-6, "maxiter": 3000})
    return max(res.x[0], 0.1), max(res.x[1], 0.1)


def _lambda_from_tt(tt):
    """Estima lambda desde P(over line) usando inversa de CDF Poisson."""
    from scipy.optimize import brentq
    try:
        lam = brentq(lambda l: (1 - poisson.cdf(tt["line"], l)) - tt["over"],
                     0.01, 15.0)
        return lam
    except Exception:
        return None


def _pick_main_total(totals_all):
    """Selecciona la línea más cercana a 2.5."""
    return min(totals_all, key=lambda t: abs(t["line"] - 2.5))


def _initial_guess(f1x2, total):
    share = f1x2["home"] / (f1x2["home"] + f1x2["away"] + 1e-9)
    total_goals = -np.log(max(1 - total["over"], 0.01)) * 2 + 1.0
    total_goals = max(1.0, min(total_goals, 8.0))
    lh0 = total_goals * (0.5 + 0.3 * (share - 0.5))
    la0 = total_goals - lh0
    return max(lh0, 0.1), max(la0, 0.1)


# ─── Estrategias principales ──────────────────────────────────────────────────

def strategy_base(match):
    """
    S_BASE: 1X2 + O/U principal + AH principal.
    Equivalente a S3 del modelo histórico.
    """
    m = match["markets"]
    if not m["moneyline"] or not m["total_main"]:
        return None
    lh, la = infer_lambdas_base(
        m["moneyline"],
        m["total_main"],
        m["spread_main"]
    )
    mat = build_matrix(lh, la)
    return mat, lh, la


def strategy_rich(match):
    """
    S_RICH: 1X2 + O/U main + O/U alt (peso 0.3) + AH main + AH alt (peso 0.3) + TT (peso 1.0).
    """
    m = match["markets"]
    if not m["moneyline"]:
        return None

    lh, la = infer_lambdas_rich(
        m["moneyline"],
        m["total_main"],
        m["totals_alt"],
        m["spread_main"],
        m["spreads_alt"],
        m["tt_home"],
        m["tt_away"],
    )
    mat = build_matrix(lh, la)
    return mat, lh, la