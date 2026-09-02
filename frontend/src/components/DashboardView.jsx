import React, { useEffect, useState } from 'react';
import { Clock, AlertTriangle, Layers, Lightbulb } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { userColor } from '../constants.jsx';

const PRIORIDADE_ORDEM = ['Urgente', 'Alta', 'Normal', 'Baixa'];
const PRIORIDADE_COR = { Urgente: '#ef4444', Alta: '#f97316', Normal: '#fbbf24', Baixa: '#10b981' };
const SUG_TILES = [
  { key: 'pendente', label: 'Pendentes', classes: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-300' },
  { key: 'aceita', label: 'Aceitas', classes: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' },
  { key: 'rejeitada', label: 'Recusadas', classes: 'bg-red-500/10 border-red-500/20 text-red-300' },
];

function StatTile({ icon, label, value, sub }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col gap-1">
      <div className="flex items-center gap-2 text-slate-400 text-xs font-bold uppercase tracking-widest">{icon} {label}</div>
      <div className="text-3xl font-black text-slate-100">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

function BarRow({ color, label, count, max, extra }) {
  const pct = max > 0 ? Math.max((count / max) * 100, count > 0 ? 4 : 0) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 shrink-0 text-xs font-bold text-slate-300 truncate">{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }}/>
      </div>
      <span className="w-8 shrink-0 text-right text-xs font-black text-slate-200">{count}</span>
      {extra}
    </div>
  );
}

export default function DashboardView({ setModal, cardsById }) {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    authFetch(`${API}/metrics`).then(r => (r.ok ? r.json() : null)).then(setMetrics);
  }, []);

  if (!metrics) {
    return <div className="absolute inset-0 flex items-center justify-center text-white/40 text-sm font-bold">Carregando métricas...</div>;
  }

  const maxColuna = Math.max(1, ...metrics.cards_por_coluna.map(c => c.total));
  const maxResp = Math.max(1, ...metrics.cards_por_responsavel.map(r => r.total));
  const prioridades = PRIORIDADE_ORDEM.map(p => ({ label: p, count: metrics.cards_por_prioridade[p] || 0 }));
  const maxPrioridade = Math.max(1, ...prioridades.map(p => p.count));

  return (
    <div className="absolute inset-0 overflow-y-auto custom-scrollbar px-4 md:px-8 py-6 space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile icon={<Layers size={14}/>} label="Total de cards" value={metrics.total_cards}/>
        <StatTile icon={<Clock size={14}/>} label="Tempo médio até concluído"
          value={metrics.tempo_medio_conclusao_dias != null ? `${metrics.tempo_medio_conclusao_dias}d` : '—'}
          sub={metrics.tempo_medio_conclusao_dias == null ? 'Sem dados ainda' : undefined}/>
        <StatTile icon={<AlertTriangle size={14}/>} label="Cards atrasados" value={metrics.cards_atrasados.length}/>
        <StatTile icon={<Lightbulb size={14}/>} label="Sugestões pendentes" value={metrics.sugestoes.pendente}/>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-bold text-slate-200">Cards por coluna</h3>
          <div className="space-y-2.5">
            {metrics.cards_por_coluna.map(c => (
              <BarRow key={c.coluna_id} color={c.cor || '#64748b'} label={c.titulo} count={c.total} max={maxColuna}/>
            ))}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-bold text-slate-200">Cards por prioridade</h3>
          <div className="space-y-2.5">
            {prioridades.map(p => (
              <BarRow key={p.label} color={PRIORIDADE_COR[p.label]} label={p.label} count={p.count} max={maxPrioridade}/>
            ))}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-bold text-slate-200">Sugestões</h3>
          <div className="grid grid-cols-3 gap-2">
            {SUG_TILES.map(t => (
              <div key={t.key} className={`rounded-xl border p-3 text-center ${t.classes}`}>
                <div className="text-2xl font-black">{metrics.sugestoes[t.key] || 0}</div>
                <div className="text-[10px] font-bold uppercase tracking-wider mt-0.5">{t.label}</div>
              </div>
            ))}
          </div>
          {metrics.sugestoes_por_decisor.length > 0 && (
            <div className="pt-2 space-y-1.5">
              {metrics.sugestoes_por_decisor.map(d => (
                <div key={d.usuario} className="flex items-center gap-2 text-xs">
                  <span className={`font-bold px-1.5 py-0.5 rounded-full ${userColor(d.usuario)}`}>{d.usuario}</span>
                  <span className="text-emerald-400 font-bold">{d.aceitas} aceitas</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-red-400 font-bold">{d.recusadas} recusadas</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-bold text-slate-200">Cards por responsável</h3>
          {metrics.cards_por_responsavel.length === 0 ? (
            <p className="text-xs text-slate-500">Nenhum card com responsável ainda.</p>
          ) : (
            <div className="space-y-2.5">
              {metrics.cards_por_responsavel.map(r => (
                <BarRow key={r.nome} color="#6366f1" label={r.nome} count={r.total} max={maxResp}
                  extra={r.atrasados > 0 && <span className="text-[10px] font-bold text-red-400 shrink-0">{r.atrasados} atrasado{r.atrasados !== 1 ? 's' : ''}</span>}/>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-2">
        <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2"><AlertTriangle size={14} className="text-red-400"/> Cards atrasados</h3>
        {metrics.cards_atrasados.length === 0 ? (
          <p className="text-xs text-slate-500">Nenhum card atrasado — tudo em dia.</p>
        ) : (
          <div className="space-y-1.5">
            {metrics.cards_atrasados.map(a => {
              const card = cardsById?.[a.id];
              return (
                <button key={a.id} onClick={() => card && setModal({ card, status: card.status })}
                  className="w-full flex items-center justify-between gap-2 p-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-left transition-colors">
                  <span className="text-sm font-bold text-slate-200 truncate">{a.titulo}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    {a.responsaveis.map(nome => (
                      <span key={nome} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${userColor(nome)}`}>{nome}</span>
                    ))}
                    <span className="text-[10px] font-bold text-red-400">{a.prazo}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
