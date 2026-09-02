import React, { useState, useMemo } from 'react';
import { X, Merge, AlertTriangle, Search, ArrowRight } from 'lucide-react';
import { API, authFetch } from '../api.js';

const CONFIRMACAO = 'CONFIRMO';

// Ação irreversível: o card de origem é apagado. A palavra digitada é o
// segundo portão (o primeiro é ser admin) e o servidor revalida os dois.
export default function MergeCardDialog({ card, allCards, allColumns, onCancel, onMerged }) {
  const [busca, setBusca] = useState('');
  const [destinoId, setDestinoId] = useState(null);
  const [confirmacao, setConfirmacao] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState('');

  const colunaPorId = useMemo(
    () => Object.fromEntries((allColumns || []).map(c => [c.id, c])),
    [allColumns]
  );

  const candidatos = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return (allCards || [])
      .filter(c => c.id !== card.id)
      .filter(c => !termo || (c.titulo || '').toLowerCase().includes(termo))
      .sort((a, b) => (a.titulo || '').localeCompare(b.titulo || ''));
  }, [allCards, card.id, busca]);

  const destino = (allCards || []).find(c => c.id === destinoId) || null;
  const podeConfirmar = destino && confirmacao.trim().toUpperCase() === CONFIRMACAO && !enviando;

  const confirmar = async () => {
    if (!podeConfirmar) return;
    setEnviando(true);
    setErro('');
    try {
      const res = await authFetch(`${API}/cards/${card.id}/merge`, {
        method: 'POST',
        body: JSON.stringify({ destino_id: destinoId, confirmacao: confirmacao.trim() }),
      });
      if (!res.ok) {
        const corpo = await res.json().catch(() => ({}));
        setErro(corpo.detail || 'Não foi possível fundir os cartões.');
        setEnviando(false);
        return;
      }
      const body = await res.json();
      onMerged(body);
    } catch (e) {
      setErro('Falha de conexão com o servidor.');
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 z-[240] flex items-center justify-center p-2 md:p-4 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">

        <div className="p-4 md:p-5 border-b border-slate-800 bg-slate-800/50 flex justify-between items-start gap-3">
          <div className="flex items-start gap-2.5 min-w-0">
            <Merge size={20} className="text-amber-400 shrink-0 mt-0.5"/>
            <div className="min-w-0">
              <h2 className="text-base md:text-lg font-bold text-slate-100">Fundir cartão</h2>
              <p className="text-xs text-slate-400 mt-0.5 break-words">
                Tudo de <span className="font-bold text-slate-200">“{card.titulo}”</span> vai para outro cartão, e este aqui é apagado.
              </p>
            </div>
          </div>
          <button onClick={onCancel} className="text-slate-500 hover:text-slate-200 shrink-0 p-1"><X size={20}/></button>
        </div>

        <div className="p-4 md:p-5 space-y-4 overflow-y-auto custom-scrollbar">

          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Cartão de destino</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"/>
              <input
                autoFocus
                value={busca}
                onChange={e => setBusca(e.target.value)}
                placeholder="Buscar cartão..."
                className="w-full bg-slate-800 text-slate-100 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:border-emerald-500"
              />
            </div>

            <div className="border border-slate-800 rounded-lg divide-y divide-slate-800 max-h-52 overflow-y-auto custom-scrollbar">
              {candidatos.length === 0 && (
                <p className="text-xs text-slate-500 p-3 text-center">Nenhum outro cartão encontrado.</p>
              )}
              {candidatos.map(c => {
                const col = colunaPorId[c.status];
                const selecionado = c.id === destinoId;
                return (
                  <button
                    key={c.id}
                    onClick={() => setDestinoId(c.id)}
                    className={`w-full text-left px-3 py-2 flex items-center gap-2 transition-colors ${selecionado ? 'bg-emerald-500/15' : 'hover:bg-slate-800'}`}
                  >
                    <span className="w-1.5 h-6 rounded-full shrink-0" style={{ backgroundColor: col?.cor || '#475569' }}/>
                    <span className="min-w-0 flex-1">
                      <span className={`block text-sm truncate ${selecionado ? 'text-emerald-300 font-bold' : 'text-slate-200'}`}>{c.titulo}</span>
                      <span className="block text-[10px] text-slate-500 truncate">{col?.titulo || 'Sem coluna'}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {destino && (
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-3 space-y-2">
              <div className="flex items-center gap-2 text-xs min-w-0">
                <span className="text-slate-400 truncate line-through">{card.titulo}</span>
                <ArrowRight size={14} className="text-amber-400 shrink-0"/>
                <span className="text-emerald-300 font-bold truncate">{destino.titulo}</span>
              </div>
              <ul className="text-[11px] text-slate-400 space-y-1 leading-relaxed">
                <li>• Etapas, comentários, responsáveis, anexos, sugestões, anotações, mapas mentais e desenhos passam para o destino.</li>
                <li>• A descrição da origem é anexada ao fim da descrição do destino.</li>
                <li>• O destino mantém prazo, prioridade e GitHub próprios; o que ele não tiver, herda da origem.</li>
                <li>• O histórico de auditoria da origem passa a viver no destino.</li>
              </ul>
            </div>
          )}

          <div className="space-y-2">
            <div className="flex items-start gap-2 text-amber-300/90 bg-amber-500/10 border border-amber-500/25 rounded-lg p-2.5">
              <AlertTriangle size={14} className="shrink-0 mt-0.5"/>
              <p className="text-[11px] leading-relaxed">
                Isso <span className="font-bold">não tem como desfazer</span>. Digite <span className="font-black tracking-wider">{CONFIRMACAO}</span> para liberar o botão.
              </p>
            </div>
            <input
              value={confirmacao}
              onChange={e => setConfirmacao(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') confirmar(); }}
              placeholder={CONFIRMACAO}
              className="w-full bg-slate-800 text-slate-100 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 tracking-widest font-bold"
            />
          </div>

          {erro && <p className="text-xs text-red-400 font-bold">{erro}</p>}
        </div>

        <div className="p-3 md:p-4 bg-slate-800 flex justify-end gap-2 border-t border-slate-700">
          <button onClick={onCancel} className="px-4 py-2 font-bold text-xs md:text-sm text-slate-300 hover:bg-slate-700 rounded-lg transition-colors">
            Cancelar
          </button>
          <button
            onClick={confirmar}
            disabled={!podeConfirmar}
            className="px-4 md:px-5 py-2 rounded-lg font-bold text-xs md:text-sm text-white transition-colors bg-amber-600 hover:bg-amber-700 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed"
          >
            {enviando ? 'Fundindo...' : 'Fundir e apagar origem'}
          </button>
        </div>
      </div>
    </div>
  );
}
