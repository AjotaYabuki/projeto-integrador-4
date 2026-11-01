"""API Flask (Render). Serve o modelo, o JSON do dashboard e recebe leituras do ESP32.

Mudanças em relação à versão anterior:
- hora local (America/Sao_Paulo): o Render roda em UTC e as features hora_sin/hora_cos do
  modelo foram treinadas com hora local, então a hora do servidor precisava ser convertida;
- GET /api/tempo_real: leituras recentes + contadores da sessão + "há quantos segundos
  chegou a última leitura" (usado pelo Dashboard.jsx);
- GET /api/ao_vivo aceita ?n= (padrão 300) em vez de devolver sempre as 2000 leituras;
- Lock para o histórico (gunicorn com threads), só os últimos 16 min entram no cálculo
  das features (equivalente ao anterior, pois a maior janela é 15 min);
- variáveis de ambiente opcionais: ESP32_KEY (exige header X-API-Key no POST),
  CORS_ORIGINS (lista separada por vírgula) e TZ_LOCAL.
"""
import json
import os
import threading
from collections import deque
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

from ml import criar_features, FEATURES, COLUNAS

BASE = Path(__file__).parent
TZ_LOCAL = os.getenv("TZ_LOCAL", "America/Sao_Paulo")
API_KEY = os.getenv("ESP32_KEY", "")
ORIGENS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
JANELA_FEATURES = pd.Timedelta(minutes=16)
FORMATO = "%Y-%m-%d %H:%M:%S"

app = Flask(__name__)
CORS(app, origins=ORIGENS if ORIGENS != ["*"] else "*")
modelo = joblib.load(BASE / "modelo.joblib")
historico = deque(maxlen=2000)  # memória: reinicia quando o Render reinicia
trava = threading.Lock()
sessao = {"inicio": None, "leituras": 0, "anomalias": 0, "energia_wh": 0.0, "ultima": None}


def agora():
    """Hora local sem fuso (mesmo formato dos CSVs usados no treino)."""
    return pd.Timestamp.now(tz=TZ_LOCAL).tz_localize(None)


def tarifa():
    try:
        d = json.loads((BASE / "dashboard_data.json").read_text(encoding="utf-8"))
        return float(d["resumo"]["tarifa"])
    except Exception:
        return 0.95


@app.get("/")
def raiz():
    return jsonify(status="ok", rotas=["/api/dashboard", "/api/tempo_real", "/api/ao_vivo", "POST /api/medicao"])


@app.get("/api/dashboard")
def dashboard():
    return jsonify(json.loads((BASE / "dashboard_data.json").read_text(encoding="utf-8")))


def _recentes():
    try:
        n = max(1, min(int(request.args.get("n", 300)), 2000))
    except ValueError:
        n = 300
    with trava:
        return list(historico)[-n:]


@app.get("/api/ao_vivo")
def ao_vivo():
    return jsonify(_recentes())


@app.get("/api/tempo_real")
def tempo_real():
    recentes = _recentes()
    with trava:
        s = dict(sessao)
    ha = None
    if s["ultima"] is not None:
        ha = round(max((agora() - s["ultima"]).total_seconds(), 0), 1)
    kwh = s["energia_wh"] / 1000
    return jsonify(
        leituras=recentes,
        ultima_ha_s=ha,
        servidor_hora=agora().strftime(FORMATO),
        sessao={"inicio": s["inicio"].strftime(FORMATO) if s["inicio"] is not None else None,
                "leituras": s["leituras"], "anomalias": s["anomalias"],
                "energia_kwh": round(kwh, 5), "custo_rs": round(kwh * tarifa(), 4)},
    )


@app.post("/api/medicao")
def medicao():
    """Corpo JSON: tensao, corrente, potencia_ativa, potencia_aparente, fator_potencia."""
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        return jsonify(erro="chave inválida"), 401
    d = request.get_json(force=True, silent=True) or {}
    try:
        nova = {c: float(d[c]) for c in COLUNAS[1:]}
    except (KeyError, TypeError, ValueError):
        return jsonify(erro="envie " + ", ".join(COLUNAS[1:])), 400
    nova["data_hora"] = agora()
    with trava:
        recentes = [h for h in historico
                    if pd.Timestamp(h["data_hora"]) >= nova["data_hora"] - JANELA_FEATURES]
        base = pd.DataFrame([{**h, "data_hora": pd.Timestamp(h["data_hora"])} for h in recentes] + [nova])
        X = criar_features(base)[FEATURES].iloc[[-1]]
        prob = float(modelo.predict_proba(X)[0][1])
        reg = {**nova, "data_hora": nova["data_hora"].strftime(FORMATO),
               "anomalia": int(prob >= 0.5), "prob_anomalia": round(prob, 3)}
        # energia da sessão: potência × tempo desde a leitura anterior (limitado a 60 s, como no treino)
        if sessao["ultima"] is None:
            sessao["inicio"] = nova["data_hora"]
        else:
            dt = min((nova["data_hora"] - sessao["ultima"]).total_seconds(), 60)
            sessao["energia_wh"] += nova["potencia_ativa"] * dt / 3600
        sessao["ultima"] = nova["data_hora"]
        sessao["leituras"] += 1
        sessao["anomalias"] += reg["anomalia"]
        historico.append(reg)
    return jsonify(reg)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
