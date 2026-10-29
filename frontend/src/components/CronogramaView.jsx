import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar, Plus } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { userColor, formatarData } from '../constants.jsx';
import { formatarDuracao } from '../cronometro.js';
import { NovaAtividadeModal, AtividadeDetalheModal } from './AtividadesCronograma.jsx';

const isoDia = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const ALTURA_ATIVIDADE = 34;  // cada faixa de atividades no topo da linha da pessoa

// Onde a atividade fica no tempo: o agendamento, ou do primeiro ao último período registrado.
function intervaloDaAtividade(a) {
  if (a.agendada_inicio) return [new Date(a.agendada_inicio), new Date(a.agendada_fim)];
  if (!a.registros.length) return null;
  const ini = a.registros[0].inicio;
  const fins = a.registros.map(r => (r.fim ? new Date(r.fim) : new Date()));
  return [new Date(ini), new Date(Math.max(...fins))];
}

// Atividades que se sobrepõem no tempo vão para faixas diferentes.
function emFaixas(atividades) {
  const faixas = [];
  const comFaixa = [];
  for (const a of [...atividades].sort((x, y) => x.intervalo[0] - y.intervalo[0])) {
    let i = faixas.findIndex(fim => fim <= a.intervalo[0]);
    if (i === -1) { i = faixas.length; faixas.push(0); }
    faixas[i] = a.intervalo[1];
    comFaixa.push({ ...a, faixa: i });
  }
  return { itens: comFaixa, total: faixas.length };
}

export default function CronogramaView({ cards, allUsers, setModal, onCronometroChange }) {
  const [offsetDays, setOffsetDays] = useState(0);
  const [windowDays, setWindowDays] = useState(28);
  const [atividades, setAtividades] = useState([]);
  const [recarregar, setRecarregar] = useState(0);
  const [janela, setJanela] = useState(null);  // null | { nova: true } | { atividade }

  const parseISO = (str) => { if (!str) return null; const [y, m, d] = str.split('-').map(Number); return new Date(y, m - 1, d); };
  const parseBR  = (str) => { if (!str) return null; const [d, m, y] = str.split('/').map(Number); return new Date(y, m - 1, d); };

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const windowStart = new Date(today); windowStart.setDate(windowStart.getDate() + offsetDays);
  const windowEnd   = new Date(windowStart); windowEnd.setDate(windowEnd.getDate() + windowDays);
  const totalRange  = windowEnd - windowStart;
  const todayPct    = Math.max(0, Math.min(100, ((today - windowStart) / totalRange) * 100));
  const days = Array.from({ length: windowDays }, (_, i) => { const d = new Date(windowStart); d.setDate(d.getDate() + i); return d; });
  const janelaIni = isoDia(windowStart);
  const janelaFim = isoDia(new Date(windowEnd.getTime() - 86400000));

  // Atividades da janela; atualiza sozinho (o cronômetro pode parar pelo
  // botão flutuante, fora desta tela).
  useEffect(() => {
    let vivo = true;
    const buscar = () => authFetch(`${API}/atividades?inicio=${janelaIni}&fim=${janelaFim}`)
      .then(r => (r.ok ? r.json() : null)).then(lista => { if (vivo && lista) setAtividades(lista); });
    buscar();
    const t = setInterval(buscar, 30000);
    return () => { vivo = false; clearInterval(t); };
  }, [janelaIni, janelaFim, recarregar]);
  const atualizar = () => setRecarregar(n => n + 1);

  const BAR_COLORS = {
    'Urgente': { bar: '#ef4444', progress: '#991b1b', text: '#fff' },
    'Alta':    { bar: '#f97316', progress: '#9a3412', text: '#fff' },
    'Normal':  { bar: '#fbbf24', progress: '#b45309', text: '#1f2937' },
    'Baixa':   { bar: '#34d399', progress: '#065f46', text: '#fff' },
  };

  const calcProgress = (card) => {
    const cl = card.checklist || [];
    if (!cl.length) return 0;
    return Math.round(cl.reduce((acc, item) => {
      const subs = item.subetapas || [];
      return acc + (subs.length === 0 ? (item.concluido ? 1 : 0) : subs.filter(s => s.concluido).length / subs.length);
    }, 0) / cl.length * 100);
  };

  const allCards = Object.values(cards);
  const cardsByUser = {};
  (allUsers || []).forEach(u => { cardsByUser[u.nome] = []; });
  allCards.forEach(card => {
    if (!card.prazo) return;
    const resp = card.responsaveis?.length > 0 ? card.responsaveis : [card.autor];
    resp.forEach(nome => {
      if (!cardsByUser[nome]) cardsByUser[nome] = [];
      if (!cardsByUser[nome].find(c => c.id === card.id)) cardsByUser[nome].push(card);
    });
  });
  Object.keys(cardsByUser).forEach(nome => { cardsByUser[nome].sort((a, b) => (a.prazo || '') < (b.prazo || '') ? -1 : 1); });

  const atividadesPorUsuario = {};
  atividades.forEach(a => {
    const intervalo = intervaloDaAtividade(a);
    if (!intervalo) return;
    (atividadesPorUsuario[a.usuario] ||= []).push({ ...a, intervalo });
  });
  Object.keys(atividadesPorUsuario).forEach(nome => { if (!cardsByUser[nome]) cardsByUser[nome] = []; });

  const semPrazo = allCards.filter(c => !c.prazo);
  const usersWithCards = Object.entries(cardsByUser).filter(([nome, uc]) => uc.length > 0 || atividadesPorUsuario[nome]);
  const DAY_SHORT  = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];
  const MONTHS_BR  = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

  const renderAtividade = (a) => {
    const [ini, fim] = a.intervalo;
    const clampIni = ini < windowStart ? windowStart : ini;
    const clampFim = fim > windowEnd ? windowEnd : fim;
    if (clampIni >= clampFim) return null;
    const leftPct = ((clampIni - windowStart) / totalRange) * 100;
    const widthPct = ((clampFim - clampIni) / totalRange) * 100;
    const soAgendada = a.registros.length === 0;
    const quando = a.agendada_inicio
      ? `${new Date(a.agendada_inicio).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })} até ${new Date(a.agendada_fim).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}`
      : '';
    return (
      <div key={a.id} onClick={() => setJanela({ atividade: a })}
        title={`${a.titulo}${quando ? ` — ${quando}` : ''}${a.total_segundos ? ` — ${formatarDuracao(a.total_segundos)} registradas` : ' — ainda sem tempo registrado'}`}
        className={`absolute rounded-lg flex items-center gap-1 overflow-hidden cursor-pointer hover:brightness-110 transition-all px-2 ${soAgendada
          ? 'border-2 border-dashed border-violet-400/80 bg-violet-500/15 text-violet-200'
          : 'bg-violet-600 text-white shadow-md'} ${a.em_andamento ? 'ring-2 ring-emerald-400 animate-pulse' : ''}`}
        style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, 1.5)}%`, top: `${a.faixa * ALTURA_ATIVIDADE + 6}px`, height: `${ALTURA_ATIVIDADE - 8}px` }}>
        <span className="text-[11px] font-bold truncate">{a.titulo}</span>
        {a.total_segundos > 0 && <span className="ml-auto shrink-0 text-[10px] font-black opacity-80">{formatarDuracao(a.total_segundos)}</span>}
      </div>
    );
  };

  const renderBar = (card, rowIndex, topo = 0) => {
    const start = parseBR(card.data_criacao) || today;
    const end   = parseISO(card.prazo);
    if (!end) return null;
    const clampStart = start < windowStart ? windowStart : start > windowEnd ? windowEnd : start;
    const clampEnd   = end > windowEnd ? windowEnd : end < windowStart ? windowStart : end;
    if (clampStart >= clampEnd) return null;
    const leftPct  = ((clampStart - windowStart) / totalRange) * 100;
    const widthPct = ((clampEnd - clampStart) / totalRange) * 100;
    const pct = calcProgress(card);
    const isPastDue = end < today && pct < 100;
    const isDone    = pct === 100;
    const colors    = BAR_COLORS[card.prioridade || 'Normal'];
    return (
      <div key={card.id} onClick={() => setModal({ card, status: card.status })}
        title={`${card.titulo} — prazo: ${formatarData(card.prazo)}${pct > 0 ? ` — ${pct}% concluído` : ''}`}
        className="absolute rounded-full flex items-center overflow-hidden cursor-pointer hover:brightness-110 transition-all shadow-md"
        style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, 2)}%`, top: `${topo + rowIndex * 44 + 8}px`, height: '30px', backgroundColor: isDone ? '#10b981' : colors.bar, boxShadow: isPastDue ? '0 0 0 2px #dc2626' : undefined, opacity: isDone ? 0.7 : 1 }}>
        {pct > 0 && pct < 100 && <div className="absolute left-0 top-0 h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: colors.progress, opacity: 0.45 }}/>}
        <span className="relative z-10 px-3 text-xs font-bold truncate" style={{ color: isDone ? '#fff' : colors.text }}>{card.titulo}</span>
        {pct > 0 && <span className="relative z-10 ml-auto pr-2.5 text-xs font-black shrink-0" style={{ color: isDone ? '#fff' : colors.text, opacity: 0.85 }}>{pct}%</span>}
      </div>
    );
  };

  return (
    <div className="absolute inset-0 flex flex-col overflow-hidden">
      {janela?.nova && (
        <NovaAtividadeModal onFechar={() => setJanela(null)} onCronometroChange={onCronometroChange}
          onCriada={() => { setJanela(null); atualizar(); }}/>
      )}
      {janela?.atividade && (
        <AtividadeDetalheModal key={janela.atividade.id} atividade={janela.atividade} onCronometroChange={onCronometroChange}
          onMudou={atualizar} onFechar={() => setJanela(null)}/>
      )}
      <div className="shrink-0 flex items-center justify-between px-6 py-2 bg-black/30 backdrop-blur-sm border-b border-white/10">
        <div className="flex items-center gap-1.5">
          {[{ label: '2 semanas', days: 14 }, { label: '1 mês', days: 30 }, { label: '3 meses', days: 90 }].map(opt => (
            <button key={opt.days} onClick={() => { setWindowDays(opt.days); setOffsetDays(0); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${windowDays === opt.days ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white' : 'bg-white/15 text-white hover:bg-white/25'}`}>
              {opt.label}
            </button>
          ))}
          <button onClick={() => setJanela({ nova: true })}
            className="ml-2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-violet-600 hover:bg-violet-500 text-white transition-colors"
            title="Registrar ou agendar uma atividade fora de card (saída de campo, reunião...)">
            <Plus size={14}/> Atividade
          </button>
        </div>
        <div className="absolute left-1/2 -translate-x-1/2 text-white/50 text-xs font-bold uppercase tracking-widest pointer-events-none">
          {windowStart.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })} — {new Date(windowEnd.getTime() - 86400000).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })}
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => setOffsetDays(d => d - windowDays)} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-white/15 text-white hover:bg-white/25 transition-colors flex items-center gap-1"><ChevronLeft size={14}/> Anterior</button>
          <button onClick={() => setOffsetDays(0)} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-white/15 text-white hover:bg-white/25 transition-colors">Hoje</button>
          <button onClick={() => setOffsetDays(d => d + windowDays)} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-white/15 text-white hover:bg-white/25 transition-colors flex items-center gap-1">Próximo <ChevronRight size={14}/></button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar">
        <div className="flex sticky top-0 z-20 bg-slate-900/95 backdrop-blur-sm shadow-lg">
          <div className="shrink-0 w-44 border-r border-white/10 px-3 py-2 flex items-end">
            <span className="text-[10px] font-black text-white/30 uppercase tracking-widest">Responsável</span>
          </div>
          <div className="flex-1 flex">
            {days.map((day, i) => {
              const isToday   = day.toDateString() === today.toDateString();
              const isWeekend = day.getDay() === 0 || day.getDay() === 6;
              const showMonth = i === 0 || day.getDate() === 1;
              return (
                <div key={i} className={`flex-1 flex flex-col items-center justify-center py-1.5 border-l border-white/5 text-center ${isToday ? 'bg-red-500/20' : isWeekend ? 'bg-white/[0.03]' : ''}`}>
                  {showMonth && <span className="text-[8px] font-black text-white/40 uppercase leading-none">{MONTHS_BR[day.getMonth()]}</span>}
                  <span className={`text-[11px] font-black leading-tight ${isToday ? 'text-red-300' : 'text-white/60'}`}>{day.getDate()}</span>
                  {windowDays <= 30 && <span className={`text-[8px] font-bold leading-none ${isToday ? 'text-red-300/70' : 'text-white/25'}`}>{DAY_SHORT[day.getDay()]}</span>}
                </div>
              );
            })}
          </div>
        </div>
        {usersWithCards.length === 0 ? (
          <div className="flex items-center justify-center h-48 text-white/40 text-sm font-bold">Nenhum card com prazo nem atividade neste período</div>
        ) : usersWithCards.map(([nome, userCards], rowI) => {
          const faixas = emFaixas(atividadesPorUsuario[nome] || []);
          const topo = faixas.total * ALTURA_ATIVIDADE;
          const rowHeight = Math.max(topo + userCards.length * 44 + (userCards.length ? 16 : 6), 64);
          return (
            <div key={nome} className={`flex border-b border-white/[0.08] ${rowI % 2 === 0 ? 'bg-white/[0.04]' : ''}`}>
              <div className="shrink-0 w-44 border-r border-white/10 px-3 flex items-center" style={{ minHeight: `${rowHeight}px` }}>
                <span className={`text-sm font-bold px-2.5 py-1 rounded-full ${userColor(nome)}`}>{nome}</span>
              </div>
              <div className="flex-1 relative" style={{ height: `${rowHeight}px` }}>
                {days.map((day, i) => (day.getDay() === 0 || day.getDay() === 6) && <div key={i} className="absolute top-0 bottom-0 bg-white/[0.03]" style={{ left: `${(i / windowDays) * 100}%`, width: `${(1 / windowDays) * 100}%` }}/>)}
                {days.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-white/[0.05]" style={{ left: `${(i / windowDays) * 100}%` }}/>)}
                {todayPct >= 0 && todayPct <= 100 && <div className="absolute top-0 bottom-0 w-0.5 bg-red-400/80 z-10" style={{ left: `${todayPct}%`, boxShadow: '0 0 8px rgba(248,113,113,0.5)' }}/>}
                {faixas.itens.map(renderAtividade)}
                {userCards.map((card, ci) => renderBar(card, ci, topo))}
              </div>
            </div>
          );
        })}
        {semPrazo.length > 0 && (
          <div className="px-6 py-4 border-t border-white/10">
            <p className="text-[10px] font-black text-white/30 uppercase tracking-widest mb-3">Sem prazo definido</p>
            <div className="flex flex-wrap gap-2">
              {semPrazo.map(card => (
                <div key={card.id} onClick={() => setModal({ card, status: card.status })} className="cursor-pointer bg-white/10 hover:bg-white/20 text-white rounded-lg px-3 py-1.5 text-xs font-bold transition-colors border border-white/10">{card.titulo}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
