"""Funções compartilhadas: leitura dos dados, features e rótulos."""
import numpy as np
import pandas as pd

LIMITE_W = 300   # acima disso a carga é considerada alta (ajuste à sua residência)
SALTO_W = 100    # variação brusca de potência entre leituras = equipamento ligou/desligou
FEATURES = ["tensao", "corrente", "potencia_ativa", "potencia_aparente", "fator_potencia",
            "potencia_reativa", "delta_p", "media_1min", "media_5min", "media_15min",
            "desvio_1min", "hora_sin", "hora_cos"]
COLUNAS = ["data_hora", "tensao", "corrente", "potencia_ativa",
           "potencia_aparente", "fator_potencia"]


def carregar_csv(caminho):
    """Lê o CSV exportado (tab, ; ou ,) com decimal vírgula ou ponto."""
    with open(caminho, encoding="utf-8-sig") as f:
        cab = f.readline()
    sep = "\t" if "\t" in cab else (";" if ";" in cab else ",")
    dec = "," if sep != "," else "."
    df = pd.read_csv(caminho, sep=sep, decimal=dec, encoding="utf-8-sig")
    extras = list(df.columns[6:])
    df = df.iloc[:, :6]
    df.columns = COLUNAS
    if extras:  # coluna opcional com rótulo real (0 = normal, 1 = anomalia)
        df["rotulo"] = pd.read_csv(caminho, sep=sep, decimal=dec, encoding="utf-8-sig").iloc[:, 6]
    df["data_hora"] = pd.to_datetime(df["data_hora"], dayfirst=True)
    return df.sort_values("data_hora").reset_index(drop=True)


def criar_features(df):
    """Janelas por tempo (1, 5 e 15 min, só passado) + hora do dia."""
    df = df.copy()
    p, s = df["potencia_ativa"], df["potencia_aparente"]
    df["potencia_reativa"] = np.sqrt(np.clip(s**2 - p**2, 0, None))
    df["delta_p"] = p.diff().fillna(0)
    serie = p.set_axis(pd.DatetimeIndex(df["data_hora"]))
    for nome, jan in (("media_1min", "1min"), ("media_5min", "5min"), ("media_15min", "15min")):
        df[nome] = serie.rolling(jan, min_periods=1).mean().to_numpy()
    df["desvio_1min"] = serie.rolling("1min", min_periods=1).std().fillna(0).to_numpy()
    h = df["data_hora"].dt.hour + df["data_hora"].dt.minute / 60
    df["hora_sin"], df["hora_cos"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
    return df


def criar_rotulo(df):
    """Rótulo por regra (use a coluna 'rotulo' do CSV se tiver rótulos reais)."""
    if "rotulo" in df:
        return df["rotulo"].astype(int)
    return ((df["potencia_ativa"] >= LIMITE_W) | (df["delta_p"].abs() >= SALTO_W)).astype(int)
