import React from 'react';
import { Square, Timer } from 'lucide-react';
import { formatarRelogio, useDecorrido } from '../cronometro.js';

// Fica no canto da tela em qualquer aba enquanto houver cronômetro rodando —
// o cabeçalho some quando o mouse sai dele, e o tempo correndo não pode sumir.
export default function CronometroFlutuante({ cronometro, onAbrirCard, onParar }) {
  const decorrido = useDecorrido(cronometro);
  if (!cronometro) return null;

  return (
    <div className="fixed bottom-4 left-4 z-[150] flex items-center gap-2 bg-slate-900/95 border border-emerald-500/40 rounded-2xl shadow-2xl backdrop-blur-md pl-3 pr-1.5 py-1.5 max-w-[calc(100vw-2rem)]">
      <span className="relative flex h-2.5 w-2.5 shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"/>
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"/>
      </span>
      <button onClick={() => onAbrirCard(cronometro.card_id)} className="min-w-0 text-left hover:opacity-80 transition-opacity" title="Abrir o card">
        <div className="text-xs font-bold text-slate-100 truncate max-w-[220px]">{cronometro.card_titulo || 'Card'}</div>
        {cronometro.etapa_texto && <div className="text-[10px] text-slate-400 truncate max-w-[220px]">{cronometro.etapa_texto}</div>}
      </button>
      <span className="flex items-center gap-1 font-mono text-sm font-bold text-emerald-300 tabular-nums shrink-0">
        <Timer size={14}/> {formatarRelogio(decorrido)}
      </span>
      <button onClick={onParar} className="shrink-0 p-2 rounded-xl bg-red-500/15 text-red-300 hover:bg-red-500/30 transition-colors" title="Parar cronômetro">
        <Square size={14} fill="currentColor"/>
      </button>
    </div>
  );
}
