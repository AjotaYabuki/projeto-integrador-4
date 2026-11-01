"""Treino do Random Forest (80/20), métricas, gráficos e JSON do dashboard."""
import json
from pathlib import Path
import joblib, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             confusion_matrix, classification_report)
from ml import carregar_csv, criar_features, criar_rotulo, FEATURES

BASE = Path(__file__).parent
TARIFA = 0.95  # R$/kWh (ajuste)
OUT = BASE / "saidas"; OUT.mkdir(exist_ok=True)

df = criar_features(carregar_csv(BASE / "dados.csv"))
df["anomalia"] = criar_rotulo(df)
if df["anomalia"].nunique() < 2:
    raise SystemExit("Só existe uma classe nos dados; ajuste LIMITE_W/SALTO_W em ml.py ou informe rótulos.")

X, y = df[FEATURES], df["anomalia"]
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

modelo = RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42, n_jobs=-1)
modelo.fit(X_tr, y_tr)
pred = modelo.predict(X_te)

met = {"acuracia": accuracy_score(y_te, pred), "precisao": precision_score(y_te, pred, zero_division=0),
       "recall": recall_score(y_te, pred, zero_division=0), "f1": f1_score(y_te, pred, zero_division=0)}
cm = confusion_matrix(y_te, pred, labels=[0, 1])
print(f"Treino: {len(X_tr)} amostras | Teste: {len(X_te)} amostras")
for k, v in met.items(): print(f"{k:9s}: {v:.4f}")
print("Matriz de confusão [[VN FP] [FN VP]]:\n", cm)
print(classification_report(y_te, pred, target_names=["Normal", "Anomalia"], zero_division=0))
joblib.dump(modelo, BASE / "modelo.joblib")

# Teste cronológico (treina nos 80% iniciais, testa nos 20% finais): estimativa mais honesta
corte = int(len(df) * 0.8)
m2 = RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42, n_jobs=-1).fit(X.iloc[:corte], y.iloc[:corte])
p2 = m2.predict(X.iloc[corte:])
cron = {"acuracia": accuracy_score(y.iloc[corte:], p2), "precisao": precision_score(y.iloc[corte:], p2, zero_division=0),
        "recall": recall_score(y.iloc[corte:], p2, zero_division=0), "f1": f1_score(y.iloc[corte:], p2, zero_division=0)}
print("Teste cronológico:", {k: round(v, 4) for k, v in cron.items()})

# ---- gráficos (PNG) ----
fig, ax = plt.subplots(figsize=(4.5, 4))
ax.imshow(cm, cmap="Blues")
for (i, j), v in np.ndenumerate(cm): ax.text(j, i, v, ha="center", va="center", fontsize=16)
ax.set_xticks([0, 1], ["Normal", "Anomalia"]); ax.set_yticks([0, 1], ["Normal", "Anomalia"])
ax.set_xlabel("Previsto"); ax.set_ylabel("Real"); ax.set_title("Matriz de confusão (teste 20%)")
fig.tight_layout(); fig.savefig(OUT / "matriz_confusao.png", dpi=130); plt.close(fig)

imp = pd.Series(modelo.feature_importances_, index=FEATURES).sort_values()
fig, ax = plt.subplots(figsize=(6, 4)); imp.plot.barh(ax=ax, color="#0f766e")
ax.set_title("Importância das variáveis"); fig.tight_layout(); fig.savefig(OUT / "importancia.png", dpi=130); plt.close(fig)

df["previsto"] = modelo.predict(X)
df["conjunto"] = "treino"; df.loc[X_te.index, "conjunto"] = "teste"
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(df["data_hora"], df["potencia_ativa"], color="#0f766e", lw=1)
a = df[df["previsto"] == 1]; ax.scatter(a["data_hora"], a["potencia_ativa"], s=10, color="#d97706", label="Anomalia")
ax.set_ylabel("Potência ativa (W)"); ax.set_title("Consumo e anomalias detectadas"); ax.legend()
fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(OUT / "serie_potencia.png", dpi=130); plt.close(fig)

# ---- JSON do dashboard ----
dt = df["data_hora"].diff().dt.total_seconds().fillna(0).clip(upper=60)
df["kwh"] = df["potencia_ativa"] * dt / 3.6e6
kwh = float(df["kwh"].sum())
bins = [0, 5, 50, 100, 300, 1e9]; nomes = ["Stand-by (<5 W)", "5–50 W", "50–100 W", "100–300 W", ">300 W"]
faixas = pd.cut(df["potencia_ativa"], bins, labels=nomes, right=False).value_counts().reindex(nomes)
dia = df.groupby(df["data_hora"].dt.date)["kwh"].sum()
hora = df.groupby(df["data_hora"].dt.hour).agg(p=("potencia_ativa", "mean"), a=("previsto", "mean"))
b = df.groupby(np.arange(len(df)) // max(1, len(df) // 1500)).agg(
    t=("data_hora", "first"), potencia=("potencia_ativa", "mean"), tensao=("tensao", "mean"),
    corrente=("corrente", "mean"), fp=("fator_potencia", "mean"), anomalia=("previsto", "max"))
dados = {
    "resumo": {"energia_kwh": round(kwh, 5), "custo_rs": round(kwh * TARIFA, 4),
               "potencia_media_w": round(df["potencia_ativa"].mean(), 1),
               "pico_w": round(df["potencia_ativa"].max(), 1),
               "tensao_media_v": round(df["tensao"].mean(), 1),
               "anomalias": int(df["previsto"].sum()), "leituras": len(df), "tarifa": TARIFA},
    "metricas": {k: round(v, 4) for k, v in met.items()},
    "metricas_cronologico": {k: round(v, 4) for k, v in cron.items()},
    "matriz_confusao": cm.tolist(),
    "split": {"treino": len(X_tr), "teste": len(X_te)},
    "importancias": {k: round(v, 4) for k, v in imp.sort_values(ascending=False).items()},
    "faixas": {k: int(v) for k, v in faixas.items()},
    "por_dia": {"dia": [d.strftime("%d/%m") for d in dia.index], "kwh": dia.round(3).tolist()},
    "perfil_horario": {"hora": [f"{h:02d}h" for h in hora.index], "potencia": hora["p"].round(1).tolist(),
                       "pct_anomalia": (hora["a"] * 100).round(1).tolist()},
    "serie": {"t": b["t"].dt.strftime("%d/%m %H:%M").tolist(), "potencia": b["potencia"].round(1).tolist(),
              "tensao": b["tensao"].round(1).tolist(), "corrente": b["corrente"].round(2).tolist(),
              "fp": b["fp"].round(2).tolist(), "anomalia": b["anomalia"].tolist()},
}
for destino in (BASE / "dashboard_data.json", BASE / "docs" / "dashboard_data.json"):
    destino.write_text(json.dumps(dados, ensure_ascii=False))
print("OK: modelo.joblib, dashboard_data.json e gráficos em saidas/")
