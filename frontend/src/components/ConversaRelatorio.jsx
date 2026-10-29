import React, { useState } from 'react';
import { Send } from 'lucide-react';
import { API, authFetch } from '../api.js';

const dataHora = (iso) => (iso ? new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');

// Conversa sobre um relatório (pessoa + dia) com um gestor — a mesma para os
// dois lados. As mensagens de quem está olhando ficam à direita.
export default function ConversaRelatorio({ autorId, data, gestorId, mensagens, onMensagens, vazio }) {
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState('');

  const mandar = async (e) => {
    e.preventDefault();
    if (!texto.trim()) return;
    setEnviando(true);
    setErro('');
    const res = await authFetch(`${API}/relatorios/conversa`, {
      method: 'POST', body: JSON.stringify({ autor_id: autorId, data, gestor_id: gestorId, texto }),
    }).catch(() => null);
    const r = await res?.json().catch(() => ({}));
    setEnviando(false);
    if (!res?.ok) { setErro(r?.detail || 'Não foi possível enviar.'); return; }
    setTexto('');
    onMensagens(r.mensagens);
  };

  return (
    <div className="space-y-2">
      {mensagens.length === 0 ? (
        <p className="text-xs text-slate-500">{vazio}</p>
      ) : (
        <ul className="space-y-1.5">
          {mensagens.map(m => (
            <li key={m.id} className={`flex ${m.eu ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-2xl px-3 py-2 ${m.eu ? 'bg-emerald-600/25 border border-emerald-500/30 rounded-br-sm' : 'bg-slate-800 border border-slate-700 rounded-bl-sm'}`}>
                <div className="text-[10px] font-bold text-slate-400 mb-0.5">{m.eu ? 'Você' : m.nome} · {dataHora(m.criado_em)}</div>
                <div className="text-sm text-slate-100 whitespace-pre-wrap break-words">{m.texto}</div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={mandar} className="flex items-end gap-2">
        <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={2} placeholder="Escreva uma resposta…"
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) mandar(e); }}
          className="flex-1 p-2 bg-slate-950 text-slate-100 border border-slate-700 rounded-xl outline-none focus:border-emerald-500 text-sm resize-y"/>
        <button type="submit" disabled={enviando || !texto.trim()} title="Enviar (Ctrl+Enter)"
          className="shrink-0 p-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-40 disabled:cursor-not-allowed">
          <Send size={16}/>
        </button>
      </form>
      {erro && <p className="text-xs font-bold text-red-400">{erro}</p>}
    </div>
  );
}
