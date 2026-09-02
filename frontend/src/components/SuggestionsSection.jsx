import React, { useEffect, useRef, useState } from 'react';
import { Lightbulb, Link2, Check, X, Trash2 } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { mentionToken, renderSuggestionText, userColor, autorRoleChips } from '../constants.jsx';

const CAMPO_LABELS = { titulo: 'Título', descricao: 'Descrição', prioridade: 'Prioridade', prazo: 'Prazo', github_url: 'Repositório GitHub' };
const STATUS_STYLE = { pendente: 'bg-yellow-500/10 border-yellow-500/20', aceita: 'bg-emerald-500/10 border-emerald-500/20', rejeitada: 'bg-red-500/10 border-red-500/20' };
const STATUS_BADGE = { pendente: 'bg-yellow-500/20 text-yellow-300', aceita: 'bg-emerald-500/20 text-emerald-300', rejeitada: 'bg-red-500/20 text-red-300' };
const STATUS_LABEL = { pendente: 'Pendente', aceita: 'Aceita', rejeitada: 'Recusada' };

function campoLabel(campoAlvo, checklist) {
  if (!campoAlvo) return '';
  if (campoAlvo.startsWith('etapa:')) {
    const item = checklist.find(i => i.id === campoAlvo.slice(6));
    return `Etapa: ${item ? item.texto : '(removida)'}`;
  }
  return CAMPO_LABELS[campoAlvo] || campoAlvo;
}

export default function SuggestionsSection({ cardId, checklist, allCards, allUsers, user, canDecide, onNavigateToCard, onNavigateToEtapa }) {
  const [sugestoes, setSugestoes] = useState([]);
  const [novoTexto, setNovoTexto] = useState('');
  const [identificacao, setIdentificacao] = useState('');
  const [mostrarProposta, setMostrarProposta] = useState(false);
  const [campoAlvo, setCampoAlvo] = useState('titulo');
  const [valorProposto, setValorProposto] = useState('');
  const [mencaoAberta, setMencaoAberta] = useState(false);
  const [mencaoBusca, setMencaoBusca] = useState('');
  const [decidindo, setDecidindo] = useState(null); // { id, status } | null
  const [prazoEntrega, setPrazoEntrega] = useState('');
  const [motivoRecusa, setMotivoRecusa] = useState('');
  const textareaRef = useRef(null);

  const recarregar = () => {
    authFetch(`${API}/cards/${cardId}/suggestions`).then(r => (r.ok ? r.json() : [])).then(setSugestoes);
  };

  useEffect(() => { if (cardId) recarregar(); }, [cardId]);

  const inserirMencao = (tipo, id, label) => {
    const token = mentionToken(tipo, id, label) + ' ';
    const ta = textareaRef.current;
    const start = ta?.selectionStart ?? novoTexto.length;
    const end = ta?.selectionEnd ?? novoTexto.length;
    const novo = novoTexto.slice(0, start) + token + novoTexto.slice(end);
    setNovoTexto(novo);
    setMencaoAberta(false);
    setMencaoBusca('');
    setTimeout(() => { ta?.focus(); if (ta) ta.selectionStart = ta.selectionEnd = start + token.length; }, 0);
  };

  const enviarSugestao = () => {
    if (!novoTexto.trim() || !identificacao.trim()) return;
    const body = { texto: novoTexto.trim(), identificacao: identificacao.trim() };
    if (mostrarProposta && valorProposto.trim()) {
      body.campo_alvo = campoAlvo;
      body.valor_proposto = valorProposto.trim();
    }
    authFetch(`${API}/cards/${cardId}/suggestions`, { method: 'POST', body: JSON.stringify(body) }).then(recarregar);
    setNovoTexto(''); setIdentificacao(''); setMostrarProposta(false); setValorProposto(''); setCampoAlvo('titulo');
  };

  const abrirDecisao = (id, status) => { setDecidindo({ id, status }); setPrazoEntrega(''); setMotivoRecusa(''); };
  const cancelarDecisao = () => setDecidindo(null);

  const confirmarDecisao = () => {
    const body = { status: decidindo.status };
    if (decidindo.status === 'aceita') {
      if (!prazoEntrega.trim()) return;
      body.prazo_entrega = prazoEntrega.trim();
    } else {
      if (!motivoRecusa.trim()) return;
      body.motivo_recusa = motivoRecusa.trim();
    }
    authFetch(`${API}/cards/${cardId}/suggestions/${decidindo.id}`, { method: 'PATCH', body: JSON.stringify(body) }).then(recarregar);
    setDecidindo(null);
  };

  const apagarSugestao = (id) => {
    if (!window.confirm('Apagar esta sugestão? Se ela tiver aplicado uma mudança no card, essa mudança será desfeita.')) return;
    authFetch(`${API}/cards/${cardId}/suggestions/${id}`, { method: 'DELETE' }).then(recarregar);
  };

  const outrosCards = (allCards || []).filter(c => c.id !== cardId && c.titulo?.toLowerCase().includes(mencaoBusca.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-slate-300 font-bold text-sm"><Lightbulb size={16}/> Sugestões</div>
      <div className="space-y-3">
        {sugestoes.map(s => (
          <div key={s.id} className={`p-3 rounded-xl border ${STATUS_STYLE[s.status] || 'bg-slate-800 border-slate-700'}`}>
            <div className="flex justify-between items-center mb-1">
              <div className="flex items-center flex-wrap gap-1.5">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${userColor(s.identificacao || s.autor)}`}>{s.identificacao || s.autor}</span>
                {autorRoleChips(s.autor, allUsers)}
                {s.identificacao && s.identificacao !== s.autor && (
                  <span className="text-[10px] text-slate-500">(conta: {s.autor})</span>
                )}
                <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded tracking-wider ${STATUS_BADGE[s.status]}`}>{STATUS_LABEL[s.status] || s.status}</span>
              </div>
            </div>
            <p className="text-sm text-slate-300">{renderSuggestionText(s.texto, { onCardClick: onNavigateToCard, onEtapaClick: onNavigateToEtapa })}</p>
            {s.campo_alvo && (
              <p className="mt-1 text-xs text-slate-400">
                Propõe alterar <span className="font-bold text-slate-200">{campoLabel(s.campo_alvo, checklist)}</span> para: <span className="font-bold text-slate-200">{s.valor_proposto}</span>
              </p>
            )}
            {s.status === 'aceita' && s.prazo_entrega && (
              <p className="mt-1 text-xs text-emerald-400">Prazo de entrega: <span className="font-bold">{s.prazo_entrega}</span></p>
            )}
            {s.status === 'rejeitada' && s.motivo_recusa && (
              <p className="mt-1 text-xs text-red-400">Motivo da recusa: <span className="font-bold">{s.motivo_recusa}</span></p>
            )}
            {canDecide && decidindo?.id !== s.id && (
              <div className="flex gap-2 mt-2">
                {s.status !== 'aceita' && (
                  <button onClick={() => abrirDecisao(s.id, 'aceita')} className="flex items-center gap-1 px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors"><Check size={12}/> Aceitar</button>
                )}
                {s.status !== 'rejeitada' && (
                  <button onClick={() => abrirDecisao(s.id, 'rejeitada')} className="flex items-center gap-1 px-2 py-1 bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-bold transition-colors"><X size={12}/> Rejeitar</button>
                )}
                <button onClick={() => apagarSugestao(s.id)} className="flex items-center gap-1 px-2 py-1 bg-slate-800 border border-slate-700 hover:bg-red-500/10 text-red-400 rounded-lg text-xs font-bold transition-colors"><Trash2 size={12}/> Apagar</button>
              </div>
            )}
            {canDecide && decidindo?.id === s.id && (
              <div className="flex flex-wrap items-center gap-2 mt-2 bg-slate-800 border border-slate-700 rounded-xl p-2">
                {decidindo.status === 'aceita' ? (
                  <>
                    <label className="text-xs text-slate-400">Prazo de entrega:</label>
                    <input type="date" autoFocus value={prazoEntrega} onChange={e => setPrazoEntrega(e.target.value)} className="text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400 [color-scheme:dark]"/>
                  </>
                ) : (
                  <>
                    <label className="text-xs text-slate-400">Motivo da recusa:</label>
                    <input type="text" autoFocus value={motivoRecusa} onChange={e => setMotivoRecusa(e.target.value)} placeholder="Explique o motivo..." className="flex-1 min-w-[140px] text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
                  </>
                )}
                <button onClick={confirmarDecisao} className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors">Confirmar</button>
                <button onClick={cancelarDecisao} className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs font-bold transition-colors">Cancelar</button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="space-y-2">
        <input value={identificacao} onChange={e => setIdentificacao(e.target.value)} className="w-full p-2 bg-slate-800 text-slate-100 border border-slate-700 rounded-xl text-sm outline-none focus:border-emerald-400" placeholder="Seu nome"/>
        <textarea ref={textareaRef} value={novoTexto} onChange={e => setNovoTexto(e.target.value)} className="w-full h-16 p-3 bg-slate-800 text-slate-100 border border-slate-700 rounded-xl text-sm outline-none focus:border-emerald-400 resize-none" placeholder="Escreva uma sugestão..."/>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <button onClick={() => setMencaoAberta(true)} className="flex items-center gap-1 px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs font-bold transition-colors"><Link2 size={12}/> Mencionar</button>
            {mencaoAberta && (
              <>
                <div className="fixed inset-0 z-[210]" onClick={() => setMencaoAberta(false)}/>
                <div className="absolute top-full mt-1 left-0 w-72 bg-slate-800 rounded-xl shadow-xl border border-slate-700 z-[220] p-3 animate-in fade-in zoom-in-95">
                  <input autoFocus value={mencaoBusca} onChange={e => setMencaoBusca(e.target.value)} placeholder="Buscar etapa ou card..." className="w-full text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400 mb-2"/>
                  <div className="max-h-48 overflow-y-auto custom-scrollbar space-y-2">
                    {checklist.length > 0 && (
                      <div>
                        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Etapas deste card</p>
                        {checklist.filter(i => i.texto?.toLowerCase().includes(mencaoBusca.toLowerCase())).map(i => (
                          <div key={i.id} onClick={() => inserirMencao('etapa', i.id, i.texto)} className="p-1.5 px-2 hover:bg-slate-700 cursor-pointer rounded text-xs text-slate-300 truncate">{i.texto}</div>
                        ))}
                      </div>
                    )}
                    <div>
                      <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Outros cards</p>
                      {outrosCards.map(c => (
                        <div key={c.id} onClick={() => inserirMencao('card', c.id, c.titulo)} className="p-1.5 px-2 hover:bg-slate-700 cursor-pointer rounded text-xs text-slate-300 truncate">{c.titulo}</div>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
          <button onClick={() => setMostrarProposta(v => !v)} className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs font-bold transition-colors">
            {mostrarProposta ? 'Remover proposta de mudança' : '+ Propor mudança de campo'}
          </button>
        </div>

        {mostrarProposta && (
          <div className="flex flex-wrap gap-2 items-center bg-slate-800 border border-slate-700 rounded-xl p-2">
            <select value={campoAlvo} onChange={e => { setCampoAlvo(e.target.value); setValorProposto(''); }} className="text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400">
              <option value="titulo">Título</option>
              <option value="descricao">Descrição</option>
              <option value="prioridade">Prioridade</option>
              <option value="prazo">Prazo</option>
              <option value="github_url">Repositório GitHub</option>
              {checklist.map(i => <option key={i.id} value={`etapa:${i.id}`}>Etapa: {i.texto}</option>)}
            </select>
            {campoAlvo === 'prioridade' ? (
              <select value={valorProposto} onChange={e => setValorProposto(e.target.value)} className="text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400">
                <option value="">Selecione...</option>
                <option value="Baixa">Baixa</option>
                <option value="Normal">Normal</option>
                <option value="Alta">Alta</option>
                <option value="Urgente">Urgente</option>
              </select>
            ) : campoAlvo === 'prazo' ? (
              <input type="date" value={valorProposto} onChange={e => setValorProposto(e.target.value)} className="text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400 [color-scheme:dark]"/>
            ) : (
              <input type="text" value={valorProposto} onChange={e => setValorProposto(e.target.value)} placeholder="Novo valor..." className="flex-1 min-w-[120px] text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
            )}
          </div>
        )}

        <button onClick={enviarSugestao} disabled={!novoTexto.trim() || !identificacao.trim()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white rounded-lg font-bold text-xs transition-colors">Enviar sugestão</button>
      </div>
    </div>
  );
}
