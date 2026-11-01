"""Simula 7 dias de uma residência (leitura a cada 10 s) com anomalias rotuladas pelo CENÁRIO.
Equipamentos normais incluem cargas altas e curtas (micro-ondas, chaleira), então uma regra
de potência não separa as classes. Gera dados.csv com a coluna Rotulo (0 normal / 1 anomalia)."""
import numpy as np, pandas as pd
rng = np.random.default_rng(7)
DT, DIAS = 10, 7
PASSOS_DIA = 86400 // DT
n = DIAS * PASSOS_DIA
t = pd.date_range("2026-10-19 00:00:00", periods=n, freq=f"{DT}s")  # segunda-feira
P, Q, y = np.zeros(n), np.zeros(n), np.zeros(n, int)
k = np.arange(n)

def add(i0, i1, w, pf, jit=0.03, mask=None):
    i0, i1 = max(i0, 0), min(i1, n)
    if i1 <= i0: return
    p = w * (1 + rng.normal(0, jit, i1 - i0))
    if mask is not None: p = p * mask[i0:i1]
    P[i0:i1] += p; Q[i0:i1] += p * np.tan(np.arccos(pf))

def idx(d, h): return d * PASSOS_DIA + int(h * 3600 / DT)

add(0, n, 4, 0.5, 0.1)                                         # stand-by
add(0, n, 130, 0.6, 0.03, mask=(((k * DT / 60 + rng.uniform(0, 50)) % 50) < 18))  # geladeira
for d in range(DIAS):
    a = rng.uniform(17.5, 19); add(idx(d, a), idx(d, rng.uniform(22.5, 24)), 36, 0.95)
    add(idx(d, 6), idx(d, 7), 24, 0.95)
    a = rng.uniform(19, 20.5); add(idx(d, a), idx(d, a + rng.uniform(1.5, 3.5)), 90, 0.8)
    a = rng.uniform(13, 15); add(idx(d, a), idx(d, a + rng.uniform(1, 3)), 55, 0.8)
    if d % 7 < 5:
        add(idx(d, 9), idx(d, 12), 150, 0.7); add(idx(d, 13), idx(d, 18), 150, 0.7)
    for h in (7.2, 12.3, 19.5):                                # micro-ondas (normal)
        i = idx(d, h + rng.uniform(-.4, .4)); add(i, i + rng.integers(6, 25), 1100, 0.95)
    i = idx(d, rng.uniform(6.3, 7)); add(i, i + rng.integers(18, 31), 1500, 1.0)  # chaleira (normal)
    for _ in range(rng.choice([1, 2])):                        # anomalias
        tipo = rng.choice(4, p=[.3, .3, .2, .2])
        if tipo == 0:   i0 = idx(d, rng.uniform(9, 21)); dur = int(rng.uniform(.5, 2) * 360); add(i0, i0 + dur, rng.uniform(400, 1200), 0.98)
        elif tipo == 1: i0 = idx(d, rng.uniform(.5, 3.5)); dur = int(rng.uniform(1, 3) * 360); add(i0, i0 + dur, rng.choice([55, 90, 150]), 0.8)
        elif tipo == 2: i0 = idx(d, rng.uniform(0, 18)); dur = int(rng.uniform(3, 6) * 360); add(i0, i0 + dur, 90, 0.6, mask=(((k * DT / 60) % 30) < 18))
        else:           i0 = idx(d, rng.uniform(0, 20)); dur = int(rng.uniform(2, 4) * 360); add(i0, i0 + dur, 25, 0.6)
        y[i0 + rng.integers(0, 7): i0 + dur] = 1               # operador rotula com pequeno atraso

y[rng.random(n) < 0.005] ^= 1                                  # ruído de rotulagem (0,5%)
Pm = np.clip(P * (1 + rng.normal(0, .01, n)) + rng.normal(0, .3, n), 0, None)
S = np.maximum(np.sqrt(P**2 + Q**2) * (1 + rng.normal(0, .01, n)), Pm)
S = np.where(S < 8, rng.normal(10, 1.2, n), S)                 # offset do ACS712 em repouso
V = 127.5 - 0.9 * S / 127 + rng.normal(0, .35, n)
V += (rng.random(n) < .001) * rng.normal(7, 2, n)              # picos espúrios do ZMPT101B
I = S / V
FP = np.clip(Pm / S, 0, 1)
df = pd.DataFrame({"Data e Hora": t.strftime("%d/%m/%Y, %H:%M:%S"), "Tensao (V)": V, "Corrente (A)": I,
    "Potencia Ativa (W)": Pm, "Potencia Aparente (VA)": S, "Fator de Potencia": FP, "Rotulo": y})
df.round({"Tensao (V)": 1, "Corrente (A)": 2, "Potencia Ativa (W)": 1, "Potencia Aparente (VA)": 1, "Fator de Potencia": 2}) \
  .to_csv("dados.csv", sep="\t", decimal=",", index=False)
print(f"{n} linhas | anomalias: {y.mean():.1%}")
