# Monitor de energia residencial com ML (ESP32 + Random Forest)

1. Salve suas leituras em `dados.csv` (6 colunas na ordem do firmware + `Rotulo` opcional).
   Opcional: 7ª coluna `rotulo` (0 normal / 1 anomalia) se tiver rótulos reais.
2. `pip install -r requirements.txt` e `python train.py` → métricas no terminal, gráficos em `saidas/`, `modelo.joblib`, `docs/dashboard_data.json`.
3. API local: `python app.py`. Teste:
   `curl -X POST localhost:5000/api/medicao -H "Content-Type: application/json" -d '{"tensao":120,"corrente":3.6,"potencia_ativa":390,"potencia_aparente":436,"fator_potencia":0.9}'`
4. **Render**: suba o repositório no GitHub → New Web Service (usa `render.yaml`; o build já roda `train.py`).
5. **GitHub Pages**: Settings → Pages → branch `main`, pasta `/docs`. Edite `API_URL` em `docs/index.html`.
6. ESP32: faça POST em `https://SEU-SERVICO.onrender.com/api/medicao` com o JSON acima (o plano free do Render "dorme" após inatividade; a 1ª chamada demora ~30 s).
