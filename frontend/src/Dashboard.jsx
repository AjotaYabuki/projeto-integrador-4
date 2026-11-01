import { useEffect, useMemo, useRef, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { Wifi, WifiOff, Pause, Play, Zap, TriangleAlert } from "lucide-react";

/* ───────── Configuração ─────────
   Defina VITE_API_URL no .env (ex.: https://SEU-SERVICO.onrender.com).
   Sem ela, usa a API local do `python app.py`. */
const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:5000").replace(/\/$/, "");
const POLL_MS = 2000;       // intervalo entre consultas ao vivo
const JANELA = 300;         // leituras mantidas nos gráficos ao vivo
const SEM_SINAL_S = 30;     // sem leitura nova por mais que isso = ESP32 parado

const COLORS = ["#4f46e5", "#06b6d4", "#f59e0b", "#ef4444", "#10b981", "#a855f7"];
const COR_ANOMALIA = "#ef4444";
const fmt = (n, d = 1) => Number(n).toLocaleString("pt-BR", { maximumFractionDigits: d });
const pct = (v) => `${(v * 100).toFixed(1).replace(".", ",")}%`;

/* ───────── Dados ───────── */
async function getJSON(url, ms) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(url, { signal: ctl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally {
    clearTimeout(t);
  }
}

/** Consulta /api/tempo_real em sequência (nunca duas requisições ao mesmo tempo). */
function useTempoReal(pausado) {
  const [estado, setEstado] = useState({ status: "conectando", leituras: [], sessao: null, ultimaHa: null });
  const primeira = useRef(true);

  useEffect(() => {
    if (pausado) return;
    let vivo = true;
    let timer;
    async function ciclo() {
      try {
        // a 1ª chamada pode levar ~30 s se o Render free estiver "dormindo"
        const d = await getJSON(`${API_URL}/api/tempo_real?n=${JANELA}`, primeira.current ? 60000 : 10000);
        primeira.current = false;
        if (!vivo) return;
        const status = !d.leituras.length ? "aguardando" : d.ultima_ha_s > SEM_SINAL_S ? "parado" : "aovivo";
        setEstado({ status, leituras: d.leituras, sessao: d.sessao, ultimaHa: d.ultima_ha_s });
      } catch {
        if (!vivo) return;
        setEstado((e) => ({ ...e, status: "offline" }));
      }
      if (vivo) timer = setTimeout(ciclo, POLL_MS);
    }
    ciclo();
    return () => { vivo = false; clearTimeout(timer); };
  }, [pausado]);

  return estado;
}

/** Resultado do último treino: API primeiro, arquivo estático como reserva. */
function useTreino() {
  const [treino, setTreino] = useState(null);
  const [fonte, setFonte] = useState("");
  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const d = await getJSON(`${API_URL}/api/dashboard`, 60000);
        if (vivo) { setTreino(d); setFonte("API"); }
      } catch {
        try {
          const d = await getJSON(`${import.meta.env.BASE_URL}dashboard_data.json`, 10000);
          if (vivo) { setTreino(d); setFonte("arquivo local (API indisponível)"); }
        } catch { /* sem dados de treino */ }
      }
    })();
    return () => { vivo = false; };
  }, []);
  return { treino, fonte };
}

/* ───────── Componentes ───────── */
function Kpi({ titulo, valor, sub, tom }) {
  const cor = tom === "alerta" ? "text-red-600" : tom === "ok" ? "text-emerald-600" : "text-slate-900";
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{titulo}</p>
      <p className={`text-2xl font-bold mt-1 ${cor}`}>{valor}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

function ChartCard({ titulo, children, wide = false, altura = "h-64" }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-xl p-4 ${wide ? "lg:col-span-2" : ""}`}>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">{titulo}</h2>
      <div className={altura}>
        <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
      </div>
    </div>
  );
}

const STATUS = {
  conectando: { txt: "Conectando à API… (pode levar ~30 s no Render free)", cor: "bg-slate-100 text-slate-600", ic: Wifi },
  aguardando: { txt: "API online · aguardando leituras do ESP32", cor: "bg-amber-100 text-amber-800", ic: Wifi },
  aovivo: { txt: "Ao vivo", cor: "bg-emerald-100 text-emerald-800", ic: Wifi },
  parado: { txt: "ESP32 sem enviar leituras", cor: "bg-amber-100 text-amber-800", ic: WifiOff },
  offline: { txt: "API indisponível", cor: "bg-red-100 text-red-700", ic: WifiOff },
};

function StatusPill({ status, ultimaHa, pausado }) {
  const s = pausado ? { txt: "Pausado", cor: "bg-slate-200 text-slate-700", ic: Pause } : STATUS[status];
  const Ic = s.ic;
  const extra = !pausado && (status === "aovivo" || status === "parado") && ultimaHa != null
    ? ` · última leitura há ${fmt(ultimaHa, 0)} s` : "";
  return (
    <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${s.cor}`}>
      <Ic size={14} /> {s.txt}{extra}
    </span>
  );
}

/* ───────── Dashboard ───────── */
export default function Dashboard() {
  const [pausado, setPausado] = useState(false);
  const { status, leituras, sessao, ultimaHa } = useTempoReal(pausado);
  const { treino, fonte } = useTreino();

  const serie = useMemo(
    () => leituras.map((x) => ({
      hora: x.data_hora.slice(11),
      potencia: x.potencia_ativa,
      anomalia: x.anomalia ? x.potencia_ativa : null,
      tensao: x.tensao,
      corrente: x.corrente,
      fp: x.fator_potencia,
    })),
    [leituras]
  );
  const ultima = leituras[leituras.length - 1];
  const eventos = useMemo(() => leituras.filter((x) => x.anomalia).slice(-6).reverse(), [leituras]);

  const tarifa = treino?.resumo?.tarifa ?? 0.95;
  const r = treino?.resumo;
  const faixas = useMemo(() => Object.entries(treino?.faixas ?? {}).map(([nome, valor]) => ({ nome, valor })), [treino]);
  const porDia = useMemo(
    () => treino ? treino.por_dia.dia.map((d, i) => ({ dia: d, kwh: treino.por_dia.kwh[i] })) : [],
    [treino]
  );
  const porHora = useMemo(
    () => treino ? treino.perfil_horario.hora.map((h, i) => ({
      hora: h, potencia: treino.perfil_horario.potencia[i], anom: treino.perfil_horario.pct_anomalia[i],
    })) : [],
    [treino]
  );
  const importancias = useMemo(
    () => Object.entries(treino?.importancias ?? {}).slice(0, 6).map(([nome, valor]) => ({ nome, valor })),
    [treino]
  );

  const temLeituras = leituras.length > 0;

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6">
      <div className="max-w-6xl mx-auto space-y-4">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Monitor de energia residencial</h1>
            <p className="text-sm text-slate-500">
              ESP32 → API Flask → Random Forest · treino: {fonte || "carregando…"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusPill status={status} ultimaHa={ultimaHa} pausado={pausado} />
            <button
              onClick={() => setPausado((p) => !p)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm hover:bg-slate-100"
            >
              {pausado ? <Play size={14} /> : <Pause size={14} />} {pausado ? "Retomar" : "Pausar"}
            </button>
          </div>
        </header>

        {status === "offline" && (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <TriangleAlert size={16} className="mt-0.5 shrink-0" />
            <span>Não consegui falar com <b>{API_URL}</b>. Confira se <code>python app.py</code> está rodando (ou a URL do Render em <code>VITE_API_URL</code>). Os dados abaixo do último treino continuam disponíveis.</span>
          </div>
        )}

        {/* ── Ao vivo ── */}
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-700"><Zap size={16} /> Tempo real</h2>

          <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
            <Kpi titulo="Potência agora" valor={ultima ? `${fmt(ultima.potencia_ativa)} W` : "–"} />
            <Kpi titulo="Tensão" valor={ultima ? `${fmt(ultima.tensao)} V` : "–"} />
            <Kpi titulo="Corrente" valor={ultima ? `${fmt(ultima.corrente, 2)} A` : "–"} />
            <Kpi titulo="Fator de potência" valor={ultima ? fmt(ultima.fator_potencia, 2) : "–"} />
            <Kpi
              titulo="Estado (modelo)"
              valor={ultima ? (ultima.anomalia ? "Anomalia" : "Normal") : "–"}
              sub={ultima ? `prob. ${pct(ultima.prob_anomalia)}` : undefined}
              tom={ultima ? (ultima.anomalia ? "alerta" : "ok") : undefined}
            />
            <Kpi
              titulo="Sessão"
              valor={sessao ? `${fmt(sessao.energia_kwh, 4)} kWh` : "–"}
              sub={sessao ? `R$ ${fmt(sessao.energia_kwh * tarifa, 3)} · ${sessao.anomalias} de ${sessao.leituras} anômalas` : undefined}
            />
          </div>

          {!temLeituras ? (
            <div className="bg-white border border-dashed border-slate-300 rounded-xl p-6 text-sm text-slate-600">
              Nenhuma leitura recebida ainda. Faça o ESP32 enviar um POST para{" "}
              <code className="bg-slate-100 px-1 rounded">{API_URL}/api/medicao</code> ou teste com{" "}
              <code className="bg-slate-100 px-1 rounded">python simular_esp32.py</code>.
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <ChartCard titulo="Potência ativa (W) e anomalias" wide altura="h-72">
                <LineChart data={serie}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="hora" fontSize={12} minTickGap={40} />
                  <YAxis fontSize={12} />
                  <Tooltip formatter={(v) => fmt(v)} />
                  <Legend />
                  <Line name="Potência (W)" type="monotone" dataKey="potencia" stroke={COLORS[1]} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line name="Anomalia" dataKey="anomalia" stroke="none" dot={{ r: 3, fill: COR_ANOMALIA, stroke: COR_ANOMALIA }} activeDot={false} isAnimationActive={false} legendType="circle" />
                </LineChart>
              </ChartCard>

              <ChartCard titulo="Tensão (V)">
                <LineChart data={serie}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="hora" fontSize={12} minTickGap={40} />
                  <YAxis fontSize={12} domain={["auto", "auto"]} />
                  <Tooltip formatter={(v) => fmt(v)} />
                  <Line type="monotone" dataKey="tensao" stroke={COLORS[0]} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                </LineChart>
              </ChartCard>

              <ChartCard titulo="Corrente (A) e fator de potência">
                <LineChart data={serie}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="hora" fontSize={12} minTickGap={40} />
                  <YAxis yAxisId="i" fontSize={12} />
                  <YAxis yAxisId="fp" orientation="right" domain={[0, 1]} fontSize={12} />
                  <Tooltip formatter={(v) => fmt(v, 2)} />
                  <Legend />
                  <Line yAxisId="i" name="Corrente (A)" type="monotone" dataKey="corrente" stroke={COLORS[4]} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  <Line yAxisId="fp" name="Fator de potência" type="monotone" dataKey="fp" stroke={COLORS[2]} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                </LineChart>
              </ChartCard>
            </div>
          )}

          {eventos.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Últimas anomalias detectadas</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="py-1 font-medium">Hora</th><th className="font-medium">Potência</th>
                    <th className="font-medium">Fator de potência</th><th className="font-medium">Prob.</th>
                  </tr>
                </thead>
                <tbody>
                  {eventos.map((x, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="py-1">{x.data_hora.slice(5)}</td>
                      <td>{fmt(x.potencia_ativa)} W</td>
                      <td>{fmt(x.fator_potencia, 2)}</td>
                      <td>{pct(x.prob_anomalia)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* ── Histórico / modelo ── */}
        {treino && (
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-700">Histórico e modelo (último treino)</h2>

            <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
              <Kpi titulo="Energia (kWh)" valor={fmt(r.energia_kwh, 2)} />
              <Kpi titulo="Custo estimado" valor={`R$ ${fmt(r.custo_rs, 2)}`} />
              <Kpi titulo="Potência média (W)" valor={fmt(r.potencia_media_w)} />
              <Kpi titulo="Pico (W)" valor={fmt(r.pico_w)} />
              <Kpi titulo="Tensão média (V)" valor={fmt(r.tensao_media_v)} />
              <Kpi titulo="Leituras anômalas" valor={`${fmt(r.anomalias, 0)} de ${fmt(r.leituras, 0)}`} tom="alerta" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <ChartCard titulo="Consumo por dia (kWh)">
                <BarChart data={porDia}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="dia" fontSize={12} />
                  <YAxis fontSize={12} />
                  <Tooltip formatter={(v) => fmt(v, 3)} />
                  <Bar dataKey="kwh" name="kWh" fill={COLORS[0]} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ChartCard>

              <ChartCard titulo="Potência média e % de anomalias por hora">
                <ComposedChart data={porHora}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="hora" fontSize={12} interval={2} />
                  <YAxis yAxisId="p" fontSize={12} />
                  <YAxis yAxisId="a" orientation="right" fontSize={12} />
                  <Tooltip formatter={(v) => fmt(v)} />
                  <Legend />
                  <Bar yAxisId="p" dataKey="potencia" name="Potência média (W)" fill={COLORS[1]} />
                  <Line yAxisId="a" type="monotone" dataKey="anom" name="% anômalas" stroke={COR_ANOMALIA} dot={false} />
                </ComposedChart>
              </ChartCard>

              <ChartCard titulo="Tempo em cada faixa de potência">
                <PieChart>
                  <Pie data={faixas} dataKey="valor" nameKey="nome" innerRadius={50} outerRadius={90}>
                    {faixas.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v) => fmt(v, 0)} />
                  <Legend />
                </PieChart>
              </ChartCard>

              <ChartCard titulo="Importância das variáveis (top 6)">
                <BarChart data={importancias} layout="vertical" margin={{ left: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" fontSize={12} />
                  <YAxis type="category" dataKey="nome" fontSize={12} width={110} />
                  <Tooltip formatter={(v) => fmt(v, 3)} />
                  <Bar dataKey="valor" name="Importância" fill={COLORS[4]} radius={[0, 6, 6, 0]} />
                </BarChart>
              </ChartCard>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Desempenho do modelo (Random Forest)</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <table className="w-full text-center">
                  <thead>
                    <tr className="text-slate-500">
                      <th className="text-left py-1 font-medium">Métrica</th>
                      <th className="font-medium">Teste aleatório 20%</th>
                      <th className="font-medium">Teste cronológico</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[["Acurácia", "acuracia"], ["Precisão", "precisao"], ["Recall", "recall"], ["F1", "f1"]].map(([n, k]) => (
                      <tr key={k} className="border-t border-slate-100">
                        <td className="text-left py-1">{n}</td>
                        <td>{pct(treino.metricas[k])}</td>
                        <td className="font-semibold">{pct(treino.metricas_cronologico[k])}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <table className="w-full text-center">
                  <thead>
                    <tr className="text-slate-500">
                      <th></th><th className="font-medium">Previsto: Normal</th><th className="font-medium">Previsto: Anomalia</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-t border-slate-100">
                      <th className="text-left py-1 font-medium">Real: Normal</th>
                      <td className="text-emerald-700 font-semibold">{treino.matriz_confusao[0][0]}</td>
                      <td className="text-red-600 font-semibold">{treino.matriz_confusao[0][1]}</td>
                    </tr>
                    <tr className="border-t border-slate-100">
                      <th className="text-left py-1 font-medium">Real: Anomalia</th>
                      <td className="text-red-600 font-semibold">{treino.matriz_confusao[1][0]}</td>
                      <td className="text-emerald-700 font-semibold">{treino.matriz_confusao[1][1]}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-500 mt-3">
                Treino: {fmt(treino.split.treino, 0)} leituras (80%) · Teste: {fmt(treino.split.teste, 0)} leituras (20%).
                O teste cronológico (treina no início do período e testa no final) é a estimativa mais realista para uso ao vivo.
              </p>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
