"""Simula o ESP32: reenvia as linhas de um CSV para a API, uma a uma, em tempo real.

Uso (na pasta do projeto, com a API rodando):
    python simular_esp32.py                                   # medicao real do ESP32, 1 leitura/s
    python simular_esp32.py --csv dados.csv --intervalo 0.2   # base de treino, mais rápido
    python simular_esp32.py --url https://SEU-SERVICO.onrender.com --chave MINHA_CHAVE --repetir
"""
import argparse
import json
import time
import urllib.error
import urllib.request

from ml import carregar_csv, COLUNAS

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost:5000")
ap.add_argument("--csv", default="esp32_real.csv")
ap.add_argument("--intervalo", type=float, default=1.0, help="segundos entre leituras")
ap.add_argument("--chave", default="", help="valor de ESP32_KEY, se a API exigir")
ap.add_argument("--max", type=int, default=0, help="parar após N leituras (0 = todas)")
ap.add_argument("--repetir", action="store_true", help="volta ao início quando o CSV acabar")
a = ap.parse_args()

df = carregar_csv(a.csv)
cab = {"Content-Type": "application/json", **({"X-API-Key": a.chave} if a.chave else {})}
enviadas = 0
while True:
    for _, r in df.iterrows():
        corpo = json.dumps({c: float(r[c]) for c in COLUNAS[1:]}).encode()
        req = urllib.request.Request(a.url.rstrip("/") + "/api/medicao", corpo, cab, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res = json.load(resp)
            print(f"{enviadas + 1:>5} {res['data_hora']}  {res['potencia_ativa']:7.1f} W  "
                  f"{'ANOMALIA' if res['anomalia'] else 'normal  '}  p={res['prob_anomalia']}")
        except (urllib.error.URLError, TimeoutError) as e:
            print("falha ao enviar:", e)
        enviadas += 1
        if a.max and enviadas >= a.max:
            raise SystemExit
        time.sleep(a.intervalo)
    if not a.repetir:
        break
