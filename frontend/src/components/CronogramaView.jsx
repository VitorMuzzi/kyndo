import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { userColor, formatarData } from '../constants.jsx';

export default function CronogramaView({ cards, allUsers, setModal }) {
  const [offsetDays, setOffsetDays] = useState(0);
  const [windowDays, setWindowDays] = useState(28);

  const parseISO = (str) => { if (!str) return null; const [y, m, d] = str.split('-').map(Number); return new Date(y, m - 1, d); };
  const parseBR  = (str) => { if (!str) return null; const [d, m, y] = str.split('/').map(Number); return new Date(y, m - 1, d); };

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const windowStart = new Date(today); windowStart.setDate(windowStart.getDate() + offsetDays);
  const windowEnd   = new Date(windowStart); windowEnd.setDate(windowEnd.getDate() + windowDays);
  const totalRange  = windowEnd - windowStart;
  const todayPct    = Math.max(0, Math.min(100, ((today - windowStart) / totalRange) * 100));
  const days = Array.from({ length: windowDays }, (_, i) => { const d = new Date(windowStart); d.setDate(d.getDate() + i); return d; });

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

  const semPrazo = allCards.filter(c => !c.prazo);
  const usersWithCards = Object.entries(cardsByUser).filter(([, uc]) => uc.length > 0);
  const DAY_SHORT  = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];
  const MONTHS_BR  = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

  const renderBar = (card, rowIndex) => {
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
        style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, 2)}%`, top: `${rowIndex * 44 + 8}px`, height: '30px', backgroundColor: isDone ? '#10b981' : colors.bar, boxShadow: isPastDue ? '0 0 0 2px #dc2626' : undefined, opacity: isDone ? 0.7 : 1 }}>
        {pct > 0 && pct < 100 && <div className="absolute left-0 top-0 h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: colors.progress, opacity: 0.45 }}/>}
        <span className="relative z-10 px-3 text-xs font-bold truncate" style={{ color: isDone ? '#fff' : colors.text }}>{card.titulo}</span>
        {pct > 0 && <span className="relative z-10 ml-auto pr-2.5 text-xs font-black shrink-0" style={{ color: isDone ? '#fff' : colors.text, opacity: 0.85 }}>{pct}%</span>}
      </div>
    );
  };

  return (
    <div className="absolute inset-0 flex flex-col overflow-hidden">
      <div className="shrink-0 flex items-center justify-between px-6 py-2 bg-black/30 backdrop-blur-sm border-b border-white/10">
        <div className="flex items-center gap-1.5">
          {[{ label: '2 semanas', days: 14 }, { label: '1 mês', days: 30 }, { label: '3 meses', days: 90 }].map(opt => (
            <button key={opt.days} onClick={() => { setWindowDays(opt.days); setOffsetDays(0); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${windowDays === opt.days ? 'bg-white text-emerald-800' : 'bg-white/15 text-white hover:bg-white/25'}`}>
              {opt.label}
            </button>
          ))}
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
        <div className="flex sticky top-0 z-20 bg-emerald-950/95 backdrop-blur-sm shadow-lg">
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
          <div className="flex items-center justify-center h-48 text-white/40 text-sm font-bold">Nenhuma atividade com prazo definido</div>
        ) : usersWithCards.map(([nome, userCards], rowI) => {
          const rowHeight = Math.max(userCards.length * 44 + 16, 64);
          return (
            <div key={nome} className={`flex border-b border-white/[0.08] ${rowI % 2 === 0 ? 'bg-white/[0.04]' : ''}`}>
              <div className="shrink-0 w-44 border-r border-white/10 px-3 flex items-center" style={{ minHeight: `${rowHeight}px` }}>
                <span className={`text-sm font-bold px-2.5 py-1 rounded-full ${userColor(nome)}`}>{nome}</span>
              </div>
              <div className="flex-1 relative" style={{ height: `${rowHeight}px` }}>
                {days.map((day, i) => (day.getDay() === 0 || day.getDay() === 6) && <div key={i} className="absolute top-0 bottom-0 bg-white/[0.03]" style={{ left: `${(i / windowDays) * 100}%`, width: `${(1 / windowDays) * 100}%` }}/>)}
                {days.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-white/[0.05]" style={{ left: `${(i / windowDays) * 100}%` }}/>)}
                {todayPct >= 0 && todayPct <= 100 && <div className="absolute top-0 bottom-0 w-0.5 bg-red-400/80 z-10" style={{ left: `${todayPct}%`, boxShadow: '0 0 8px rgba(248,113,113,0.5)' }}/>}
                {userCards.map((card, ci) => renderBar(card, ci))}
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
