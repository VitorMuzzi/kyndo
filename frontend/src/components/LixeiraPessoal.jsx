import React, { useEffect, useState } from 'react';
import { RotateCcw, Trash2, X } from 'lucide-react';
import { API, authFetch } from '../api.js';

const DIA_MS = 24 * 60 * 60 * 1000;

// Lixeira de notas/desenhos do próprio usuário: o que ele excluiu fica aqui
// por 30 dias e volta com um clique, sem depender de quem vê a auditoria.
export default function LixeiraPessoal({ tipo, onRecuperado }) {
  const [aberta, setAberta] = useState(false);
  const [itens, setItens] = useState(null);
  const [erro, setErro] = useState('');
  const [recuperando, setRecuperando] = useState(null);

  const carregar = () => authFetch(`${API}/lixeira?tipo=${tipo}`)
    .then(r => (r.ok ? r.json() : []))
    .then(lista => {
      const agora = Date.now();
      setItens(lista.map(i => ({ ...i, dias: Math.max(0, Math.ceil((new Date(i.expira_em) - agora) / DIA_MS)) })));
    })
    .catch(() => setItens([]));

  useEffect(() => {
    if (aberta) carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- recarrega só ao abrir
  }, [aberta]);

  const recuperar = async (item) => {
    setErro('');
    setRecuperando(item.id);
    try {
      const res = await authFetch(`${API}/lixeira/${item.id}/recuperar`, { method: 'POST' });
      if (!res.ok) {
        const corpo = await res.json().catch(() => ({}));
        setErro(corpo.detail || 'Não foi possível recuperar.');
        return;
      }
      setItens(lista => lista.filter(i => i.id !== item.id));
      onRecuperado?.(item.alvo_id);
    } finally {
      setRecuperando(null);
    }
  };

  const nome = tipo === 'nota' ? 'notas' : 'desenhos';

  return (
    <div className="relative">
      <button onClick={() => setAberta(a => !a)} title={`${nome[0].toUpperCase()}${nome.slice(1)} excluídos nos últimos 30 dias`}
        className={`w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] font-bold transition-colors ${aberta ? 'bg-white/15 text-white' : 'text-white/40 hover:text-white/80 hover:bg-white/10'}`}>
        <Trash2 size={12}/> Lixeira
      </button>
      {aberta && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAberta(false)}/>
          <div className="absolute bottom-full mb-2 left-0 w-72 bg-slate-800 rounded-xl shadow-2xl border border-slate-700 z-50 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Lixeira · 30 dias</span>
              <button onClick={() => setAberta(false)} className="text-slate-500 hover:text-slate-200"><X size={14}/></button>
            </div>
            <div className="max-h-72 overflow-y-auto custom-scrollbar">
              {itens === null && <p className="px-3 py-3 text-xs text-slate-500">Carregando...</p>}
              {itens?.length === 0 && <p className="px-3 py-3 text-xs text-slate-500">Nenhum{tipo === 'nota' ? 'a nota excluída' : ' desenho excluído'}.</p>}
              {itens?.map(i => (
                <div key={i.id} className="flex items-center gap-2 px-3 py-2 hover:bg-slate-700/50">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold text-slate-200 truncate">{i.titulo || 'Sem título'}</p>
                    <p className="text-[10px] text-slate-500">some em {i.dias} dia{i.dias !== 1 ? 's' : ''}</p>
                  </div>
                  <button onClick={() => recuperar(i)} disabled={recuperando === i.id}
                    className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-bold bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/40 disabled:opacity-50 transition-colors">
                    <RotateCcw size={11}/> Recuperar
                  </button>
                </div>
              ))}
            </div>
            {erro && <p className="px-3 py-2 text-[11px] text-amber-300 border-t border-slate-700">{erro}</p>}
          </div>
        </>
      )}
    </div>
  );
}
