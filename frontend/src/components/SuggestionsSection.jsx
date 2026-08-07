import React, { useEffect, useRef, useState } from 'react';
import { Lightbulb, Link2, Check, X, Trash2 } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { mentionToken, renderSuggestionText, userColor, autorRoleChips } from '../constants.jsx';

const CAMPO_LABELS = { titulo: 'Título', descricao: 'Descrição', prioridade: 'Prioridade', prazo: 'Prazo', github_url: 'Repositório GitHub' };
const STATUS_STYLE = { pendente: 'bg-yellow-50 border-yellow-100', aceita: 'bg-emerald-50 border-emerald-100', rejeitada: 'bg-red-50 border-red-100' };
const STATUS_BADGE = { pendente: 'bg-yellow-200 text-yellow-800', aceita: 'bg-emerald-200 text-emerald-800', rejeitada: 'bg-red-200 text-red-700' };
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
      <div className="flex items-center gap-2 text-gray-700 font-bold text-sm"><Lightbulb size={16}/> Sugestões</div>
      <div className="space-y-3">
        {sugestoes.map(s => (
          <div key={s.id} className={`p-3 rounded-xl border ${STATUS_STYLE[s.status] || 'bg-gray-50 border-gray-100'}`}>
            <div className="flex justify-between items-center mb-1">
              <div className="flex items-center flex-wrap gap-1.5">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${userColor(s.identificacao || s.autor)}`}>{s.identificacao || s.autor}</span>
                {autorRoleChips(s.autor, allUsers)}
                {s.identificacao && s.identificacao !== s.autor && (
                  <span className="text-[10px] text-gray-400">(conta: {s.autor})</span>
                )}
                <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded tracking-wider ${STATUS_BADGE[s.status]}`}>{STATUS_LABEL[s.status] || s.status}</span>
              </div>
            </div>
            <p className="text-sm text-gray-700">{renderSuggestionText(s.texto, { onCardClick: onNavigateToCard, onEtapaClick: onNavigateToEtapa })}</p>
            {s.campo_alvo && (
              <p className="mt-1 text-xs text-gray-500">
                Propõe alterar <span className="font-bold text-gray-700">{campoLabel(s.campo_alvo, checklist)}</span> para: <span className="font-bold text-gray-700">{s.valor_proposto}</span>
              </p>
            )}
            {s.status === 'aceita' && s.prazo_entrega && (
              <p className="mt-1 text-xs text-emerald-700">Prazo de entrega: <span className="font-bold">{s.prazo_entrega}</span></p>
            )}
            {s.status === 'rejeitada' && s.motivo_recusa && (
              <p className="mt-1 text-xs text-red-600">Motivo da recusa: <span className="font-bold">{s.motivo_recusa}</span></p>
            )}
            {canDecide && decidindo?.id !== s.id && (
              <div className="flex gap-2 mt-2">
                {s.status !== 'aceita' && (
                  <button onClick={() => abrirDecisao(s.id, 'aceita')} className="flex items-center gap-1 px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors"><Check size={12}/> Aceitar</button>
                )}
                {s.status !== 'rejeitada' && (
                  <button onClick={() => abrirDecisao(s.id, 'rejeitada')} className="flex items-center gap-1 px-2 py-1 bg-white border border-gray-200 hover:bg-gray-100 text-gray-600 rounded-lg text-xs font-bold transition-colors"><X size={12}/> Rejeitar</button>
                )}
                <button onClick={() => apagarSugestao(s.id)} className="flex items-center gap-1 px-2 py-1 bg-white border border-gray-200 hover:bg-red-50 text-red-500 rounded-lg text-xs font-bold transition-colors"><Trash2 size={12}/> Apagar</button>
              </div>
            )}
            {canDecide && decidindo?.id === s.id && (
              <div className="flex flex-wrap items-center gap-2 mt-2 bg-white border border-gray-200 rounded-xl p-2">
                {decidindo.status === 'aceita' ? (
                  <>
                    <label className="text-xs text-gray-500">Prazo de entrega:</label>
                    <input type="date" autoFocus value={prazoEntrega} onChange={e => setPrazoEntrega(e.target.value)} className="text-xs border rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
                  </>
                ) : (
                  <>
                    <label className="text-xs text-gray-500">Motivo da recusa:</label>
                    <input type="text" autoFocus value={motivoRecusa} onChange={e => setMotivoRecusa(e.target.value)} placeholder="Explique o motivo..." className="flex-1 min-w-[140px] text-xs border rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
                  </>
                )}
                <button onClick={confirmarDecisao} className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors">Confirmar</button>
                <button onClick={cancelarDecisao} className="px-2 py-1 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-xs font-bold transition-colors">Cancelar</button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="space-y-2">
        <input value={identificacao} onChange={e => setIdentificacao(e.target.value)} className="w-full p-2 bg-gray-50 border border-gray-200 rounded-xl text-sm outline-none focus:border-emerald-400" placeholder="Seu nome"/>
        <textarea ref={textareaRef} value={novoTexto} onChange={e => setNovoTexto(e.target.value)} className="w-full h-16 p-3 bg-gray-50 border border-gray-200 rounded-xl text-sm outline-none focus:border-emerald-400 resize-none" placeholder="Escreva uma sugestão..."/>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <button onClick={() => setMencaoAberta(true)} className="flex items-center gap-1 px-2 py-1 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-xs font-bold transition-colors"><Link2 size={12}/> Mencionar</button>
            {mencaoAberta && (
              <>
                <div className="fixed inset-0 z-[210]" onClick={() => setMencaoAberta(false)}/>
                <div className="absolute top-full mt-1 left-0 w-72 bg-white rounded-xl shadow-xl border border-gray-200 z-[220] p-3 animate-in fade-in zoom-in-95">
                  <input autoFocus value={mencaoBusca} onChange={e => setMencaoBusca(e.target.value)} placeholder="Buscar etapa ou card..." className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400 mb-2"/>
                  <div className="max-h-48 overflow-y-auto custom-scrollbar space-y-2">
                    {checklist.length > 0 && (
                      <div>
                        <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Etapas deste card</p>
                        {checklist.filter(i => i.texto?.toLowerCase().includes(mencaoBusca.toLowerCase())).map(i => (
                          <div key={i.id} onClick={() => inserirMencao('etapa', i.id, i.texto)} className="p-1.5 px-2 hover:bg-gray-100 cursor-pointer rounded text-xs text-gray-700 truncate">{i.texto}</div>
                        ))}
                      </div>
                    )}
                    <div>
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Outros cards</p>
                      {outrosCards.map(c => (
                        <div key={c.id} onClick={() => inserirMencao('card', c.id, c.titulo)} className="p-1.5 px-2 hover:bg-gray-100 cursor-pointer rounded text-xs text-gray-700 truncate">{c.titulo}</div>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
          <button onClick={() => setMostrarProposta(v => !v)} className="px-2 py-1 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-xs font-bold transition-colors">
            {mostrarProposta ? 'Remover proposta de mudança' : '+ Propor mudança de campo'}
          </button>
        </div>

        {mostrarProposta && (
          <div className="flex flex-wrap gap-2 items-center bg-gray-50 border border-gray-200 rounded-xl p-2">
            <select value={campoAlvo} onChange={e => { setCampoAlvo(e.target.value); setValorProposto(''); }} className="text-xs border rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400">
              <option value="titulo">Título</option>
              <option value="descricao">Descrição</option>
              <option value="prioridade">Prioridade</option>
              <option value="prazo">Prazo</option>
              <option value="github_url">Repositório GitHub</option>
              {checklist.map(i => <option key={i.id} value={`etapa:${i.id}`}>Etapa: {i.texto}</option>)}
            </select>
            {campoAlvo === 'prioridade' ? (
              <select value={valorProposto} onChange={e => setValorProposto(e.target.value)} className="text-xs border rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400">
                <option value="">Selecione...</option>
                <option value="Baixa">Baixa</option>
                <option value="Normal">Normal</option>
                <option value="Alta">Alta</option>
                <option value="Urgente">Urgente</option>
              </select>
            ) : campoAlvo === 'prazo' ? (
              <input type="date" value={valorProposto} onChange={e => setValorProposto(e.target.value)} className="text-xs border rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
            ) : (
              <input type="text" value={valorProposto} onChange={e => setValorProposto(e.target.value)} placeholder="Novo valor..." className="flex-1 min-w-[120px] text-xs border rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
            )}
          </div>
        )}

        <button onClick={enviarSugestao} disabled={!novoTexto.trim() || !identificacao.trim()} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg font-bold text-xs transition-colors">Enviar sugestão</button>
      </div>
    </div>
  );
}
