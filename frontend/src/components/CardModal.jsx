import React, { useState, useEffect } from 'react';
import { X, AlignLeft, CheckSquare, Circle, CheckCircle2, Tag, MessageSquare, Send, Calendar, ChevronDown, ChevronRight, MoreHorizontal, FileText, PenLine, ExternalLink, Network } from 'lucide-react';
import { PRIORIDADES_BADGE, userColor, formatarData, hasPermission, autorRoleChips, renderTextWithLinks, GitHubIcon } from '../constants.jsx';
import { API, authFetch } from '../api.js';
import DrawingThumbnail from './DrawingThumbnail.jsx';
import SuggestionsSection from './SuggestionsSection.jsx';

export default function CardModal({ card, col, user, allUsers, allCards, onClose, onSave, onDelete, onOpenLinkedItem, onNavigateToCard }) {
  const [titulo, setTitulo] = useState(card?.titulo || '');
  const [desc, setDesc] = useState(card?.descricao || '');
  const [checklist, setChecklist] = useState(card?.checklist || []);
  const [prioridade, setPrioridade] = useState(card?.prioridade || 'Normal');
  const [comentarios, setComentarios] = useState(card?.comentarios || []);
  const [prazo, setPrazo] = useState(card?.prazo || '');
  const [responsaveis, setResponsaveis] = useState(
    card?.responsaveis?.length > 0 ? card.responsaveis : (card?.autor ? [card.autor] : [user.nome])
  );
  const [githubUrl, setGithubUrl] = useState(card?.github_url || '');
  const [novaSubtarefa, setNovaSubtarefa] = useState('');
  const [novoComentario, setNovoComentario] = useState('');
  const [prioridadeAberto, setPrioridadeAberto] = useState(false);
  const [githubMenuAberto, setGithubMenuAberto] = useState(false);
  const [githubUrlTemp, setGithubUrlTemp] = useState('');
  const [editingItemId, setEditingItemId] = useState(null);
  const [editingItemText, setEditingItemText] = useState('');
  const [expandedItemId, setExpandedItemId] = useState(null);
  const [editingSubItemId, setEditingSubItemId] = useState(null);
  const [editingSubItemText, setEditingSubItemText] = useState('');
  const [novaSubetapa, setNovaSubetapa] = useState('');
  const [linkedNotes, setLinkedNotes] = useState([]);
  const [linkedDrawings, setLinkedDrawings] = useState([]);

  useEffect(() => {
    if (!card?.id) return;
    authFetch(`${API}/notes?card_id=${card.id}`).then(r => r.ok ? r.json() : []).then(setLinkedNotes);
    authFetch(`${API}/drawings?card_id=${card.id}`).then(r => r.ok ? r.json() : []).then(setLinkedDrawings);
  }, [card?.id]);

  const canEditCard = hasPermission(user, 'editar_card');
  const canDeleteCard = hasPermission(user, 'excluir_card');
  const canEditPrioridade = hasPermission(user, 'editar_prioridade');
  const canEditPrazo = hasPermission(user, 'editar_prazo');
  const canManageEtapas = hasPermission(user, 'gerenciar_etapas');
  const canCompleteEtapas = canManageEtapas || hasPermission(user, 'concluir_etapas');
  const canManageResponsaveis = hasPermission(user, 'gerenciar_responsaveis');
  const canDecideSugestoes = hasPermission(user, 'decidir_sugestoes');
  const isAuthor = card?.autor === user.nome;

  // Preserved exactly as before RBAC: authors keep self-service editing rights
  // in public columns / on their own new card, on top of whatever their cargos grant.
  const podeEditarDescricao = canEditCard || (col?.publica && (isAuthor || !card?.id));
  const podeDeletar = card?.id && (canDeleteCard || (isAuthor && col?.id === 'col-1'));
  const mostrarPrioridade = canEditPrioridade || prioridade !== 'Normal' || col?.id !== 'col-1';
  const mostrarPrazo = canEditPrazo || prazo;
  const mostrarEtapas = canCompleteEtapas || checklist.length > 0;

  const normalizeGithubUrl = (url) => {
    const trimmed = url.trim();
    if (!trimmed) return '';
    return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  };

  const handleDescChange = (e) => { setDesc(e.target.value.replace(/(^|\n)-\s/g, '$1• ')); };
  const handleDescKeyDown = (e) => {
    if (e.key === 'Enter') {
      const pos = e.target.selectionStart;
      const lines = desc.substring(0, pos).split('\n');
      const curLine = lines[lines.length - 1];
      if (curLine === '• ') { e.preventDefault(); setDesc(desc.substring(0, pos - 2) + '\n' + desc.substring(pos)); setTimeout(() => e.target.selectionStart = e.target.selectionEnd = pos - 1, 0); return; }
      if (curLine.startsWith('• ')) { e.preventDefault(); setDesc(desc.substring(0, pos) + '\n• ' + desc.substring(pos)); setTimeout(() => e.target.selectionStart = e.target.selectionEnd = pos + 3, 0); return; }
    }
  };

  const novoId = (prefixo) => `${prefixo}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const addSubtarefa = () => { if (!novaSubtarefa.trim() || !canManageEtapas) return; setChecklist([...checklist, { id: novoId('sub'), texto: novaSubtarefa, concluido: false, criador: user.nome }]); setNovaSubtarefa(''); };
  const addComentario = () => { if (!novoComentario.trim()) return; const dataAtual = new Date().toLocaleDateString('pt-BR', { hour: '2-digit', minute: '2-digit' }); setComentarios([...comentarios, { id: novoId('msg'), autor: user.nome, texto: novoComentario, data: dataAtual }]); setNovoComentario(''); };

  const percentual = checklist.length > 0 ? Math.round(
    checklist.reduce((acc, item) => {
      const subs = item.subetapas || [];
      return acc + (subs.length === 0 ? (item.concluido ? 1 : 0) : subs.filter(s => s.concluido).length / subs.length);
    }, 0) / checklist.length * 100
  ) : 0;

  return (
    <div className="fixed inset-0 bg-black/60 z-[200] flex items-center justify-center p-2 md:p-4 backdrop-blur-sm">
      <div className="bg-white w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[95vh]">
        <div className="p-4 md:p-6 border-b flex justify-between items-start bg-gray-50/50">
          <div className="flex-grow flex flex-col gap-2 min-w-0">
            <div className="flex justify-between items-center w-full pr-4">
              <input disabled={!podeEditarDescricao} value={titulo} onChange={e => setTitulo(e.target.value)} className={`text-xl md:text-2xl font-bold w-full outline-none bg-transparent ${!podeEditarDescricao ? 'text-gray-600' : ''}`} placeholder="Título da demanda..." />
              {mostrarPrioridade && (
                <div className="flex items-center gap-1 md:gap-2 shrink-0 ml-2 relative">
                  <Tag size={14} className="text-gray-400 hidden md:block"/>
                  {canEditPrioridade ? (
                    <div className="relative">
                      <div onClick={() => setPrioridadeAberto(!prioridadeAberto)} className={`flex items-center gap-1 text-[10px] md:text-xs font-bold uppercase rounded-lg px-2 py-1 outline-none cursor-pointer transition-colors ${PRIORIDADES_BADGE[prioridade]}`}>
                        {prioridade} <ChevronDown size={12}/>
                      </div>
                      {prioridadeAberto && (
                        <>
                          <div className="fixed inset-0 z-[210]" onClick={() => setPrioridadeAberto(false)}/>
                          <div className="absolute top-full mt-1 right-0 w-32 bg-white rounded-xl shadow-xl border border-gray-200 z-[220] overflow-hidden animate-in fade-in zoom-in-95">
                            {['Baixa', 'Normal', 'Alta', 'Urgente'].map(prio => (
                              <div key={prio} onClick={() => { setPrioridade(prio); setPrioridadeAberto(false); }} className={`p-2 px-3 hover:bg-gray-100 cursor-pointer flex items-center transition-colors ${prioridade === prio ? 'bg-gray-50' : ''}`}>
                                <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded w-full text-center ${PRIORIDADES_BADGE[prio]}`}>{prio}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <span className={`text-[10px] md:text-xs font-bold uppercase rounded-lg px-2 py-1 ${PRIORIDADES_BADGE[prioridade]}`}>{prioridade}</span>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2 md:gap-4 text-[10px] md:text-xs font-bold uppercase tracking-widest mt-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-gray-400 text-[10px] md:text-xs font-bold uppercase tracking-widest">Responsável:</span>
                {responsaveis.map(nome => (
                  <span key={nome} className={`flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded-full ${userColor(nome)}`}>
                    {nome}
                    {canManageResponsaveis && responsaveis.length > 1 && (
                      <button onClick={e => { e.stopPropagation(); setResponsaveis(responsaveis.filter(r => r !== nome)); }} className="hover:text-red-600 leading-none">×</button>
                    )}
                  </span>
                ))}
                {canManageResponsaveis && (
                  <select value="" onChange={e => { if (e.target.value && !responsaveis.includes(e.target.value)) setResponsaveis([...responsaveis, e.target.value]); }} className="text-[10px] font-bold border border-dashed border-gray-300 rounded-full px-1.5 py-0.5 outline-none bg-transparent text-gray-500 cursor-pointer">
                    <option value="">+ add</option>
                    {(allUsers || []).filter(u => !responsaveis.includes(u.nome)).map(u => <option key={u.id} value={u.nome}>{u.nome}</option>)}
                  </select>
                )}
              </div>
              {card?.data_criacao && <p className="text-gray-400 hidden md:block">Criado em: {card.data_criacao}</p>}
              {mostrarPrazo && (
                <div className="flex items-center gap-1 bg-white border border-gray-200 px-2 py-1 rounded text-gray-600">
                  <Calendar size={12} className="text-orange-500"/>
                  {canEditPrazo ? (
                    <input type="date" value={prazo} onChange={e => setPrazo(e.target.value)} className="bg-transparent outline-none cursor-pointer text-gray-800"/>
                  ) : (
                    <span className="font-bold text-gray-800">{formatarData(prazo)}</span>
                  )}
                </div>
              )}
              <div className="relative flex items-center gap-1 shrink-0">
                {githubUrl && (
                  <a href={githubUrl} target="_blank" rel="noopener noreferrer" title="Abrir repositório no GitHub" className="flex items-center justify-center w-8 h-8 bg-white border border-gray-200 rounded-lg text-gray-800 hover:text-black hover:border-gray-400 transition-colors">
                    <GitHubIcon size={20}/>
                  </a>
                )}
                <button onClick={() => { setGithubUrlTemp(githubUrl); setGithubMenuAberto(true); }} title="Configurar repositório GitHub" className="flex items-center justify-center w-7 h-7 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors">
                  <MoreHorizontal size={16}/>
                </button>
                {githubMenuAberto && (
                  <>
                    <div className="fixed inset-0 z-[210]" onClick={() => setGithubMenuAberto(false)}/>
                    <div className="absolute top-full mt-1 right-0 w-64 bg-white rounded-xl shadow-xl border border-gray-200 z-[220] p-3 animate-in fade-in zoom-in-95">
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-2">Repositório GitHub</p>
                      <div className="flex gap-1.5">
                        <input autoFocus type="text" value={githubUrlTemp} onChange={e => setGithubUrlTemp(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') { setGithubUrl(normalizeGithubUrl(githubUrlTemp)); setGithubMenuAberto(false); } if (e.key === 'Escape') setGithubMenuAberto(false); }}
                          placeholder="github.com/usuario/repo" className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
                        <button onClick={() => { setGithubUrl(normalizeGithubUrl(githubUrlTemp)); setGithubMenuAberto(false); }} className="px-2 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors">OK</button>
                      </div>
                      {githubUrl && (
                        <button onClick={() => { setGithubUrl(''); setGithubUrlTemp(''); setGithubMenuAberto(false); }} className="mt-2 text-[10px] text-red-400 hover:text-red-600 font-bold">Remover repositório</button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 shrink-0 p-1"><X size={24}/></button>
        </div>

        <div className="p-4 md:p-8 space-y-6 md:space-y-8 overflow-y-auto custom-scrollbar">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-gray-700 font-bold text-sm"><AlignLeft size={16}/> Descrição</div>
            {podeEditarDescricao ? (
              <textarea value={desc} onChange={handleDescChange} onKeyDown={handleDescKeyDown} className="w-full h-24 md:h-32 p-3 md:p-4 bg-gray-50 rounded-xl border border-gray-200 outline-none focus:bg-white text-sm font-mono shadow-inner resize-none" placeholder="Dica: Use '- ' para criar listas..."/>
            ) : (
              <div className="w-full min-h-[6rem] p-3 md:p-4 bg-gray-50 rounded-xl border border-gray-200 text-sm font-mono shadow-inner whitespace-pre-wrap break-words">
                {desc ? renderTextWithLinks(desc) : <span className="text-gray-400">Apenas visualização.</span>}
              </div>
            )}
          </div>

          {mostrarEtapas && (
            <>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-gray-700 font-bold text-sm"><CheckSquare size={16}/> Etapas</div>
                  {checklist.length > 0 && <span className="text-sm font-bold text-gray-500">{percentual}%</span>}
                </div>
                {checklist.length > 0 && <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden"><div className={`h-full transition-all duration-300 ${percentual === 100 ? 'bg-emerald-500' : 'bg-teal-500'}`} style={{ width: `${percentual}%` }}/></div>}
                <div className="space-y-1">
                  {checklist.map(item => {
                    const subetapas = item.subetapas || [];
                    const isExpanded = expandedItemId === item.id;
                    return (
                      <div key={item.id} id={`etapa-${item.id}`} className="mb-1">
                        <div className="flex items-center gap-2 group/item">
                          <button disabled={!canCompleteEtapas} onClick={() => { const nowDone = !item.concluido; setChecklist(checklist.map(i => i.id === item.id ? { ...i, concluido: nowDone, concluidoPor: nowDone ? user.nome : null, subetapas: nowDone ? (i.subetapas||[]).map(s => ({...s, concluido: true, concluidoPor: user.nome})) : (i.subetapas||[]) } : i)); }} className={`${!canCompleteEtapas ? 'cursor-default' : 'cursor-pointer hover:scale-110 transition-transform'} shrink-0`}>
                            {item.concluido ? <CheckCircle2 size={16} className="text-emerald-500"/> : <Circle size={16} className="text-gray-300"/>}
                          </button>
                          {canManageEtapas && editingItemId === item.id ? (
                            <input value={editingItemText} onChange={e => setEditingItemText(e.target.value)} onBlur={() => { if (editingItemText.trim()) setChecklist(checklist.map(i => i.id === item.id ? {...i, texto: editingItemText.trim()} : i)); setEditingItemId(null); }} onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') setEditingItemId(null); }} className="flex-1 min-w-0 text-sm border-b-2 border-emerald-400 outline-none bg-transparent text-gray-700 py-0.5" autoFocus/>
                          ) : (
                            <span className={`flex-1 min-w-0 text-sm ${item.concluido ? 'text-gray-400 line-through' : 'text-gray-700'} ${canManageEtapas ? 'cursor-pointer hover:text-emerald-600' : ''}`} onClick={() => { if (canManageEtapas) { setEditingItemId(item.id); setEditingItemText(item.texto); } }}>{item.texto}</span>
                          )}
                          <div className="flex items-center gap-1 shrink-0">
                            {item.concluido && item.concluidoPor && item.concluidoPor === item.criador
                              ? <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(item.concluidoPor)}`}>✓ {item.concluidoPor}</span>
                              : <>{item.criador && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ${userColor(item.criador)}`}>{item.criador}</span>}{item.concluido && item.concluidoPor && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(item.concluidoPor)}`}>✓ {item.concluidoPor}</span>}</>}
                            {canManageEtapas && <button onClick={() => setChecklist(checklist.filter(i => i.id !== item.id))} className="opacity-0 group-hover/item:opacity-100 p-0.5 text-red-400 hover:text-red-600 transition-all"><X size={14}/></button>}
                            <button onClick={() => {
                              const abrindo = !isExpanded;
                              setExpandedItemId(abrindo ? item.id : null);
                              setNovaSubetapa('');
                              if (abrindo && item.notas_nao_vista && card?.id) {
                                authFetch(`${API}/cards/${card.id}/items/${item.id}/seen`, { method: 'POST' });
                                setChecklist(cl => cl.map(i => i.id === item.id ? { ...i, notas_nao_vista: false } : i));
                              }
                            }} className="relative p-0.5 text-gray-400 hover:text-emerald-500 transition-colors">
                              {item.notas_nao_vista && !isExpanded && (
                                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-red-500 rounded-full ring-1 ring-white animate-pulse" title="Nova observação nesta etapa"/>
                              )}
                              {isExpanded ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}
                            </button>
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="ml-7 mt-1 mb-2 pl-3 border-l-2 border-emerald-300 space-y-2">
                            <textarea value={item.notas || ''} onChange={e => setChecklist(checklist.map(i => i.id === item.id ? {...i, notas: e.target.value} : i))} disabled={!canManageEtapas} placeholder={canManageEtapas ? 'Observações...' : 'Sem observações.'} className="w-full h-20 p-2 bg-gray-50 rounded-lg border border-gray-200 outline-none focus:bg-white text-sm resize-none"/>
                            {canManageEtapas && (
                              <div className="flex gap-2">
                                <input value={novaSubetapa} onChange={e => setNovaSubetapa(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && novaSubetapa.trim()) { setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: [...(i.subetapas||[]), {id: novoId('sub'), texto: novaSubetapa.trim(), concluido: false, criador: user.nome}]} : i)); setNovaSubetapa(''); } }} className="flex-1 p-1.5 border rounded text-xs outline-none focus:border-emerald-400" placeholder="Adicionar sub-etapa..."/>
                                <button onClick={() => { if (!novaSubetapa.trim()) return; setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: [...(i.subetapas||[]), {id: novoId('sub'), texto: novaSubetapa.trim(), concluido: false, criador: user.nome}]} : i)); setNovaSubetapa(''); }} className="px-3 py-1.5 bg-emerald-600 text-white rounded text-xs font-bold">Add</button>
                              </div>
                            )}
                          </div>
                        )}
                        {subetapas.length > 0 && (
                          <div className="ml-7 pl-3 mt-1 border-l-2 border-gray-200 space-y-1">
                            {subetapas.map(sub => (
                              <div key={sub.id} className="flex items-center gap-2 group/sub">
                                <button disabled={!canCompleteEtapas} onClick={() => setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: (i.subetapas||[]).map(s => s.id === sub.id ? {...s, concluido: !s.concluido, concluidoPor: !s.concluido ? user.nome : null} : s)} : i))} className={`shrink-0 ${!canCompleteEtapas ? 'cursor-default' : 'cursor-pointer hover:scale-110 transition-transform'}`}>
                                  {sub.concluido ? <CheckCircle2 size={16} className="text-emerald-500"/> : <Circle size={16} className="text-gray-300"/>}
                                </button>
                                {canManageEtapas && editingSubItemId === sub.id ? (
                                  <input value={editingSubItemText} onChange={e => setEditingSubItemText(e.target.value)} onBlur={() => { if (editingSubItemText.trim()) setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: (i.subetapas||[]).map(s => s.id === sub.id ? {...s, texto: editingSubItemText.trim()} : s)} : i)); setEditingSubItemId(null); }} onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') setEditingSubItemId(null); }} className="flex-1 min-w-0 text-sm border-b border-emerald-400 outline-none bg-transparent py-0.5" autoFocus/>
                                ) : (
                                  <span className={`flex-1 min-w-0 text-sm ${sub.concluido ? 'text-gray-400 line-through' : 'text-gray-600'} ${canManageEtapas ? 'cursor-pointer hover:text-emerald-600' : ''}`} onClick={() => { if (canManageEtapas) { setEditingSubItemId(sub.id); setEditingSubItemText(sub.texto); } }}>{sub.texto}</span>
                                )}
                                <div className="flex items-center gap-1 shrink-0">
                                  {sub.concluido && sub.concluidoPor && sub.concluidoPor === sub.criador
                                    ? <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(sub.concluidoPor)}`}>✓ {sub.concluidoPor}</span>
                                    : <>{sub.criador && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ${userColor(sub.criador)}`}>{sub.criador}</span>}{sub.concluido && sub.concluidoPor && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(sub.concluidoPor)}`}>✓ {sub.concluidoPor}</span>}</>}
                                  {canManageEtapas && <button onClick={() => setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: (i.subetapas||[]).filter(s => s.id !== sub.id)} : i))} className="opacity-0 group-hover/sub:opacity-100 p-0.5 text-red-400 hover:text-red-600 transition-all"><X size={14}/></button>}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                {canManageEtapas && (
                  <div className="flex flex-row items-center gap-2 pt-2 w-full">
                    <input value={novaSubtarefa} onChange={e => setNovaSubtarefa(e.target.value)} onKeyDown={e => e.key === 'Enter' && addSubtarefa()} className="flex-grow min-w-0 p-2 border rounded-lg text-sm outline-none focus:border-emerald-400" placeholder="Adicionar etapa..."/>
                    <button onClick={addSubtarefa} className="shrink-0 px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-bold shadow-md">Add</button>
                  </div>
                )}
              </div>
              <hr className="border-gray-200"/>
            </>
          )}

          {(linkedNotes.length > 0 || linkedDrawings.length > 0) && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-gray-700 font-bold text-sm"><FileText size={16}/> Notas e Desenhos vinculados</div>
              <div className="flex flex-wrap gap-2">
                {linkedNotes.map(n => (
                  <button key={n.id} onClick={() => onOpenLinkedItem?.('nota', n.id)}
                    className="flex flex-col gap-1.5 p-2 w-36 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg text-gray-700 transition-colors">
                    <div className="w-32 h-32 rounded bg-white border border-gray-200 p-2 overflow-hidden">
                      {n.tipo === 'canvas' ? (
                        <div className="w-full h-full flex items-center justify-center">
                          <Network size={36} className="text-blue-400"/>
                        </div>
                      ) : (
                        <p className="text-[10px] text-gray-500 leading-snug line-clamp-6 whitespace-pre-wrap break-words text-left">
                          {n.conteudo || 'Nota vazia'}
                        </p>
                      )}
                    </div>
                    <span className="flex items-center gap-1 text-xs font-bold truncate">
                      <FileText size={12} className="text-emerald-600 shrink-0"/> <span className="truncate">{n.titulo || 'Sem título'}</span> <ExternalLink size={11} className="text-gray-400 shrink-0"/>
                    </span>
                  </button>
                ))}
                {linkedDrawings.map(d => (
                  <button key={d.id} onClick={() => onOpenLinkedItem?.('desenho', d.id)}
                    className="flex flex-col gap-1.5 p-2 w-36 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg text-gray-700 transition-colors">
                    {d.data ? (
                      <DrawingThumbnail src={d.data} size={128}/>
                    ) : (
                      <div className="w-32 h-32 flex items-center justify-center rounded" style={{ background: '#0f172a' }}>
                        <PenLine size={20} className="text-emerald-400"/>
                      </div>
                    )}
                    <span className="flex items-center gap-1 text-xs font-bold truncate">
                      <span className="truncate">{d.titulo || 'Sem título'}</span> <ExternalLink size={11} className="text-gray-400 shrink-0"/>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {card?.id && (
            <>
              <SuggestionsSection
                cardId={card.id}
                checklist={checklist}
                allCards={allCards}
                allUsers={allUsers}
                user={user}
                canDecide={canDecideSugestoes}
                onNavigateToCard={onNavigateToCard}
                onNavigateToEtapa={(itemId) => {
                  setExpandedItemId(itemId);
                  setTimeout(() => document.getElementById(`etapa-${itemId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 0);
                }}
              />
              <hr className="border-gray-200"/>
            </>
          )}

          <div className="space-y-4">
            <div className="flex items-center gap-2 text-gray-700 font-bold text-sm"><MessageSquare size={16}/> Comentários</div>
            <div className="space-y-3">
              {comentarios.map(msg => {
                const roleChips = autorRoleChips(msg.autor, allUsers);
                const isAuthorComment = msg.autor === (card?.autor || user.nome);
                let boxClass = 'bg-gray-50 border-gray-100';
                if (roleChips) boxClass = 'bg-orange-50 border-orange-100';
                else if (isAuthorComment) boxClass = 'bg-emerald-50 border-emerald-100';
                return (
                  <div key={msg.id} className={`p-3 rounded-xl border ${boxClass}`}>
                    <div className="flex justify-between items-center mb-1">
                      <div className="flex items-center flex-wrap gap-1">
                        <span className="text-xs font-bold text-gray-800">{msg.autor}</span>
                        {roleChips || (isAuthorComment && (
                          <span className="text-[9px] bg-emerald-200 text-emerald-800 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Solicitante</span>
                        ))}
                      </div>
                      <span className="text-[10px] text-gray-400 font-semibold">{msg.data}</span>
                    </div>
                    <p className="text-sm text-gray-700">{msg.texto}</p>
                  </div>
                );
              })}
            </div>
            <div className="flex flex-row gap-2 items-center mt-2 w-full">
              <textarea value={novoComentario} onChange={e => setNovoComentario(e.target.value)} className="flex-grow min-w-0 p-3 bg-gray-50 border border-gray-200 rounded-xl text-sm outline-none focus:border-emerald-400 resize-none h-16 md:h-20" placeholder="Escreva um comentário..."/>
              <button onClick={addComentario} className="shrink-0 w-16 h-16 md:w-20 md:h-20 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-colors flex items-center justify-center"><Send size={18} className="ml-1"/></button>
            </div>
          </div>
        </div>

        <div className="p-3 md:p-4 bg-gray-100 flex justify-end gap-2 md:gap-3 border-t">
          {podeDeletar && <button onClick={() => onDelete(card.id)} className="text-red-600 px-2 py-2 md:px-4 font-bold text-[10px] md:text-sm mr-auto hover:bg-red-50 rounded-lg transition-colors">Excluir</button>}
          <button onClick={onClose} className="px-3 md:px-5 py-2 font-bold text-xs md:text-sm hover:bg-gray-200 rounded-lg transition-colors">Fechar</button>
          <button onClick={() => onSave({ ...card, titulo, descricao: desc, checklist, prioridade, comentarios, prazo, autor: card?.autor || user.nome, responsaveis, github_url: githubUrl })} className="px-4 md:px-6 py-2 bg-emerald-600 text-white rounded-lg font-bold text-xs md:text-sm shadow-lg hover:bg-emerald-700 transition-colors">Salvar Tudo</button>
        </div>
      </div>
    </div>
  );
}
