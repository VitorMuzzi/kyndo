import React, { useState, useEffect, useRef } from 'react';
import { Search, X } from 'lucide-react';
import { PRIORIDADES_BADGE, userColor } from '../constants.jsx';

export default function SearchModal({ cards, cols, onSelect, onClose }) {
  const [query, setQuery]   = useState('');
  const [cursor, setCursor] = useState(0);
  const inputRef  = useRef(null);
  const listRef   = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const colMap = Object.fromEntries((cols || []).map(c => [c.id, c]));

  const q = query.trim().toLowerCase();
  const results = q.length < 1 ? [] : Object.values(cards).filter(c => {
    return (
      c.titulo?.toLowerCase().includes(q) ||
      c.descricao?.toLowerCase().includes(q) ||
      c.autor?.toLowerCase().includes(q) ||
      (c.responsaveis || []).some(r => r.toLowerCase().includes(q))
    );
  }).slice(0, 30);

  useEffect(() => { setCursor(0); }, [query]);

  const select = (card) => { onSelect(card); onClose(); };

  const onKey = (e) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c + 1, results.length - 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)); }
    if (e.key === 'Enter' && results[cursor]) select(results[cursor]);
  };

  useEffect(() => {
    const el = listRef.current?.children[cursor];
    el?.scrollIntoView({ block: 'nearest' });
  }, [cursor]);

  return (
    <div className="fixed inset-0 z-[300] flex items-start justify-center pt-[12vh] px-4" onClick={onClose}>
      <div className="w-full max-w-xl bg-emerald-950/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/15 overflow-hidden"
        onClick={e => e.stopPropagation()}>

        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10">
          <Search size={18} className="text-white/40 shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder="Buscar cards..."
            className="flex-1 bg-transparent text-white placeholder-white/30 text-sm outline-none"
          />
          {query && (
            <button onClick={() => setQuery('')} className="text-white/30 hover:text-white/60 transition-colors">
              <X size={16} />
            </button>
          )}
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[60vh] overflow-y-auto custom-scrollbar py-1">
          {q.length < 1 ? (
            <p className="text-white/25 text-xs text-center py-8 font-mono">
              Digite para buscar por título, descrição ou responsável
            </p>
          ) : results.length === 0 ? (
            <p className="text-white/25 text-xs text-center py-8">Nenhum card encontrado</p>
          ) : results.map((card, i) => {
            const col = colMap[card.status];
            const active = i === cursor;
            return (
              <button key={card.id} onClick={() => select(card)} onMouseEnter={() => setCursor(i)}
                className={`w-full text-left px-4 py-3 flex items-start gap-3 transition-colors ${active ? 'bg-white/10' : 'hover:bg-white/5'}`}>

                {/* Column color dot */}
                <div className="mt-1 w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: col?.cor || '#6b7280' }} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-white text-sm font-bold truncate">{card.titulo}</span>
                    <span className={`text-[10px] font-black px-1.5 py-0.5 rounded shrink-0 ${PRIORIDADES_BADGE[card.prioridade || 'Normal']}`}>
                      {card.prioridade || 'Normal'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className="text-white/35 text-[11px]">{col?.titulo || card.status}</span>
                    {(card.responsaveis || []).map(nome => (
                      <span key={nome} className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${userColor(nome)}`}>{nome}</span>
                    ))}
                  </div>
                  {card.descricao && q && card.descricao.toLowerCase().includes(q) && (
                    <p className="text-white/30 text-[11px] mt-1 truncate">{card.descricao}</p>
                  )}
                </div>
              </button>
            );
          })}
          {results.length === 30 && (
            <p className="text-white/20 text-[10px] text-center py-2">Mostrando os primeiros 30 resultados</p>
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-white/8 flex items-center gap-4 text-white/20 text-[10px] font-mono">
          <span>↑↓ navegar</span>
          <span>Enter abrir</span>
          <span>Esc fechar</span>
        </div>
      </div>
    </div>
  );
}
