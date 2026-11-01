# Dashboard em tempo real — como usar

Copie estes arquivos para a pasta `energia-ml` (substituem `app.py` e `render.yaml`; o resto é novo).

## Rodar local (3 terminais)
1. API:        `python app.py`                       → http://localhost:5000
2. ESP32 fake: `python simular_esp32.py`             (reenvia `esp32_real.csv`; copie o CSV da medição para a pasta com esse nome, ou use `--csv dados.csv`)
3. Dashboard:  `cd frontend && npm install && npm run dev`  → http://localhost:5173

## Produção
- Render: suba o repositório; defina `ESP32_KEY` (opcional) e `CORS_ORIGINS` com a URL onde o dashboard estiver.
- Frontend: copie `.env.example` para `.env`, troque `VITE_API_URL` pela URL do Render e rode `npm run build` (pasta `dist/`).
- ESP32: POST em `/api/medicao` (se usar `ESP32_KEY`, envie o header `X-API-Key`).

## Novo na API
- `GET /api/tempo_real?n=300` — últimas leituras + contadores da sessão + segundos desde a última leitura.
- `GET /api/ao_vivo?n=300` — continua existindo (o `docs/index.html` antigo segue funcionando).
- Hora do servidor convertida para America/Sao_Paulo (o modelo usa hora do dia como variável).
