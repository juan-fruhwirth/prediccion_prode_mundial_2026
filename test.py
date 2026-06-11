import json
import numpy as np
from strategy import strategy_base, strategy_rich, best_score_max_ev

with open("wc2026_markets.json") as f:
    matches = json.load(f)

# South Korea vs Czechia
match = next(m for m in matches if m["home"] == "South Korea")
mat, lh, la = strategy_base(match)

print(f"λ_home: {lh:.3f}, λ_away: {la:.3f}")
print(f"\nTop 10 scores por probabilidad:")
cells = [(i,j,mat[i,j]) for i in range(11) for j in range(11)]
cells.sort(key=lambda x: -x[2])
for i,j,p in cells[:10]:
    print(f"  {i}-{j}: {p*100:.2f}%")

print(f"\nTop 10 scores por EV:")
# Recalcular EV manualmente
i = np.arange(11)
result_matrix = np.where(i[:,None] > i[None,:], 0,
                np.where(i[:,None] == i[None,:], 1, 2))
ev_matrix = np.zeros((11,11))
for res_val in [0,1,2]:
    mask = result_matrix == res_val
    p_result_total = float(np.sum(mat[mask]))
    idxs = np.argwhere(mask)
    for ii,jj in idxs:
        p_exact = mat[ii,jj]
        p_result = p_result_total - p_exact
        ev_matrix[ii,jj] = p_exact * 6 + p_result * 3

evs = [(i,j,ev_matrix[i,j]) for i in range(11) for j in range(11)]
evs.sort(key=lambda x: -x[2])
for i,j,ev in evs[:10]:
    print(f"  {i}-{j}: EV={ev:.4f} (P={mat[i,j]*100:.2f}%)")