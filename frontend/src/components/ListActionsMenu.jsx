import React, { useEffect, useRef } from 'react';
import { X, Plus, Archive, Palette, Settings, CheckCircle2, Circle, Lock, Unlock } from 'lucide-react';
import { hasPermission } from '../constants.jsx';

export default function ListActionsMenu({ col, user, onClose, onAddCard, onArchiveList, onUpdateCol }) {
  const menuRef = useRef();

  useEffect(() => {
    const handleClickOutside = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) onClose(); };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  if (!hasPermission(user, 'gerenciar_colunas')) return null;

  return (
    <div ref={menuRef} className="absolute top-12 right-2 w-64 bg-slate-800 rounded-xl shadow-2xl border border-slate-700 z-[100] p-3 space-y-1 animate-in fade-in zoom-in-95">
      <div className="flex justify-between items-center pb-2 mb-2 border-b border-slate-700">
        <h4 className="text-sm font-semibold text-slate-200 text-center flex-grow">Configurações</h4>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-200 rounded-full p-1 hover:bg-slate-700"><X size={16}/></button>
      </div>

      <button onClick={() => { onUpdateCol({ ...col, publica: !col.publica }); onClose(); }} className="w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-3 text-slate-100 hover:bg-slate-700 transition-colors font-semibold">
        {col.publica ? <Lock size={16} className="text-orange-400"/> : <Unlock size={16} className="text-emerald-400"/>}
        {col.publica ? 'Tornar Privada' : 'Tornar Pública'}
      </button>

      <button onClick={() => { onAddCard(); onClose(); }} className="w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-3 text-slate-100 hover:bg-slate-700 transition-colors">
        <Plus size={16} className="text-slate-400"/> Adicionar cartão
      </button>

      <div className="pt-2 mt-2 border-t border-slate-700">
        <div className="flex items-center gap-2 text-xs text-slate-500 font-bold uppercase tracking-wider mb-1 px-1"><Settings size={14}/> Automações</div>
        <button onClick={() => onUpdateCol({ ...col, auto_andamento: !col.auto_andamento })} className="w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between text-slate-300 hover:bg-slate-700 transition-colors">
          <span>Receber iniciadas {'>0%'}</span>
          {col.auto_andamento ? <CheckCircle2 size={16} className="text-emerald-500"/> : <Circle size={16} className="text-slate-600"/>}
        </button>
        <button onClick={() => onUpdateCol({ ...col, auto_concluido: !col.auto_concluido })} className="w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between text-slate-300 hover:bg-slate-700 transition-colors">
          <span>Receber concluídas 100%</span>
          {col.auto_concluido ? <CheckCircle2 size={16} className="text-green-500"/> : <Circle size={16} className="text-slate-600"/>}
        </button>
      </div>

      <button onClick={() => { onArchiveList(); onClose(); }} className="w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-3 text-red-400 hover:bg-red-500/10 mt-2 transition-colors border-t border-slate-700">
        <Archive size={16} className="text-red-400"/> Arquivar lista
      </button>

      <div className="pt-3 mt-2 border-t border-slate-700 space-y-2">
        <div className="flex items-center gap-2 text-sm text-slate-300 font-medium"><Palette size={16} className="text-slate-400"/> Cor da Lista</div>
        <div className="grid grid-cols-6 gap-2 pt-1">
          {[
            '#ebecf0','#94a3b8','#fecaca','#f87171','#fed7aa','#fb923c',
            '#fef08a','#fde047','#bbf7d0','#4ade80','#99f6e4','#2dd4bf',
            '#bfdbfe','#60a5fa','#e9d5ff','#c084fc','#fbcfe8','#f472b6',
          ].map(color => (
            <button key={color} onClick={() => onUpdateCol({ ...col, cor: color })} className="w-full h-6 rounded border border-black/10 hover:scale-110 transition-transform" style={{ backgroundColor: color }} />
          ))}
        </div>
      </div>
    </div>
  );
}
