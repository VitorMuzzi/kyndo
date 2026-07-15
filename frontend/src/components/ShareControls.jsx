import React from 'react';
import { Link2, Globe, Users } from 'lucide-react';
import { userColor } from '../constants.jsx';

export default function ShareControls({ item, allUsers, allCards, isOwner, onChange, currentUserId }) {
  const compartilhados = item.compartilhado_com || [];
  const linkedCard = allCards.find(c => c.id === item.card_id) || null;

  const setCardId = (cardId) => {
    if (!isOwner) return;
    onChange(cardId ? { card_id: cardId } : { card_id: null, publico: false });
  };

  const togglePublico = () => {
    if (!isOwner || !item.card_id) return;
    onChange({ publico: !item.publico });
  };

  const setNivel = (userId, nivel) => {
    if (!isOwner) return;
    onChange({ compartilhado_com: compartilhados.map(s => s.user_id === userId ? { ...s, nivel } : s) });
  };

  const removeShare = (userId) => {
    if (!isOwner) return;
    onChange({ compartilhado_com: compartilhados.filter(s => s.user_id !== userId) });
  };

  const addShare = (userId) => {
    if (!isOwner || !userId || compartilhados.some(s => s.user_id === userId)) return;
    onChange({ compartilhado_com: [...compartilhados, { user_id: userId, nivel: 'ver' }] });
  };

  const availableUsers = (allUsers || []).filter(u =>
    u.id !== currentUserId && !compartilhados.some(s => s.user_id === u.id)
  );

  return (
    <div className="flex flex-wrap items-center gap-2 md:gap-3 px-5 py-2 border-b border-white/10 bg-black/10 text-xs">
      <div className="flex items-center gap-1.5">
        <Link2 size={13} className="text-white/35 shrink-0"/>
        <select
          value={item.card_id || ''}
          onChange={e => setCardId(e.target.value || null)}
          disabled={!isOwner}
          className="bg-white/10 text-white/80 rounded-lg px-2 py-1 text-[11px] font-bold outline-none disabled:opacity-60 disabled:cursor-not-allowed max-w-[160px]"
          style={{ colorScheme: 'dark' }}
        >
          <option value="" style={{ background: '#1e293b' }}>Nenhuma tarefa vinculada</option>
          {(allCards || []).map(c => (
            <option key={c.id} value={c.id} style={{ background: '#1e293b' }}>{c.titulo}</option>
          ))}
        </select>
        {!isOwner && linkedCard && <span className="text-white/30">({linkedCard.titulo})</span>}
      </div>

      <button
        onClick={togglePublico}
        disabled={!isOwner || !item.card_id}
        title={!item.card_id ? 'Vincule a uma tarefa primeiro para poder marcar como público' : 'Responsáveis da tarefa vinculada ganham acesso automático'}
        className={`flex items-center gap-1 px-2 py-1 rounded-lg font-bold text-[11px] transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
          item.publico ? 'bg-emerald-500/80 text-white' : 'bg-white/10 text-white/50 hover:bg-white/15'
        }`}
      >
        <Globe size={12}/> Público
      </button>

      <div className="flex items-center gap-1.5 flex-wrap">
        <Users size={13} className="text-white/35 shrink-0"/>
        {compartilhados.map(s => {
          const u = (allUsers || []).find(x => x.id === s.user_id);
          return (
            <span key={s.user_id} className={`flex items-center gap-1 pl-1.5 pr-1 py-0.5 rounded-full text-[10px] font-bold ${userColor(u?.nome || '')}`}>
              {u?.nome || '?'}
              {isOwner ? (
                <select value={s.nivel} onChange={e => setNivel(s.user_id, e.target.value)}
                  className="bg-transparent text-[10px] font-bold outline-none cursor-pointer">
                  <option value="ver">ver</option>
                  <option value="editar">editar</option>
                </select>
              ) : (
                <span className="opacity-70">· {s.nivel}</span>
              )}
              {isOwner && (
                <button onClick={() => removeShare(s.user_id)} className="hover:text-red-600 leading-none px-0.5">×</button>
              )}
            </span>
          );
        })}
        {isOwner && (
          <select value="" onChange={e => addShare(e.target.value)}
            className="text-[10px] font-bold border border-dashed border-white/25 rounded-full px-1.5 py-0.5 outline-none bg-transparent text-white/50 cursor-pointer">
            <option value="" style={{ background: '#1e293b' }}>+ compartilhar</option>
            {availableUsers.map(u => <option key={u.id} value={u.id} style={{ background: '#1e293b' }}>{u.nome}</option>)}
          </select>
        )}
      </div>
    </div>
  );
}
