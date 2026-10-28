import React, { useState, useEffect } from 'react';
import { AlertTriangle, ArrowLeft, AlignLeft, CheckSquare, Circle, CheckCircle2, MessageSquare, Send, Calendar, ChevronDown, ChevronRight, MoreHorizontal, FileText, PenLine, ExternalLink, Network, Repeat, Merge, ListTree, Minus, Plus, Eye, EyeOff, Trash2 } from 'lucide-react';
import { PRIORIDADES_BADGE, userColor, formatarData, hasPermission, autorRoleChips, renderTextWithLinks, GitHubIcon } from '../constants.jsx';
import { API, authFetch } from '../api.js';
import DrawingThumbnail from './DrawingThumbnail.jsx';
import SuggestionsSection from './SuggestionsSection.jsx';
import AttachmentsSection from './AttachmentsSection.jsx';
import GithubPrSection from './GithubPrSection.jsx';
import MergeCardDialog from './MergeCardDialog.jsx';
import EtapasEditor from './EtapasEditor.jsx';
import TempoSection from './TempoSection.jsx';

// Bloco da barra lateral: um rótulo pequeno e o conteúdo. Fica fora do
// componente — definido dentro, ele remontaria os campos a cada tecla.
function Campo({ rotulo, children }) {
  return (
    <div className="space-y-1.5">
      <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{rotulo}</div>
      {children}
    </div>
  );
}

const PAINEL = 'bg-slate-900 border border-slate-800 rounded-2xl p-4 md:p-5';

// Caixa de confirmação por cima da tela do card. Esc ou clique fora fecham.
function Dialogo({ titulo, children, acoes, onFechar }) {
  useEffect(() => {
    const tecla = (e) => { if (e.key === 'Escape') onFechar(); };
    document.addEventListener('keydown', tecla);
    return () => document.removeEventListener('keydown', tecla);
  }, [onFechar]);
  return (
    <div className="fixed inset-0 z-[230] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" onClick={onFechar}>
      <div className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-5 space-y-3" onClick={e => e.stopPropagation()}>
        <h3 className="text-base font-black text-slate-100 flex items-center gap-2">{titulo}</h3>
        <div className="text-sm text-slate-400 leading-relaxed">{children}</div>
        <div className="flex flex-wrap justify-end gap-2 pt-2">{acoes}</div>
      </div>
    </div>
  );
}

export default function CardPage({ card, col, allColumns, user, allUsers, allCards, onClose, onSave, onDelete, onOpenLinkedItem, onNavigateToCard, onMerged, cronometro, onCronometroChange, guardaSaidaRef }) {
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
  const [recorrente, setRecorrente] = useState(card?.recorrente || false);
  const [recorrenciaDias, setRecorrenciaDias] = useState(card?.recorrencia_dias || 7);
  const [recorrenciaPreset, setRecorrenciaPreset] = useState(
    [1, 7, 15, 30].includes(card?.recorrencia_dias) ? card.recorrencia_dias : 'custom'
  );

  // Retrato de tudo que o "Salvar Tudo" grava. Comparado com o da abertura,
  // diz se há alteração que se perderia ao sair. notas_nao_vista é marca de
  // leitura (abrir uma observação), não edição — fica de fora.
  const retrato = () => JSON.stringify({
    titulo, desc, prioridade, comentarios, prazo, responsaveis, githubUrl, recorrente, recorrenciaDias,
    checklist: checklist.map(i => ({ ...i, notas_nao_vista: undefined })),
  });
  const [retratoInicial] = useState(retrato);
  const temAlteracoes = retrato() !== retratoInicial;
  const [saidaPendente, setSaidaPendente] = useState(null);  // o que fazer se a pessoa confirmar a saída
  const [confirmandoExclusao, setConfirmandoExclusao] = useState(false);
  const [salvando, setSalvando] = useState(false);

  const [novaSubtarefa, setNovaSubtarefa] = useState('');
  const [novoComentario, setNovoComentario] = useState('');
  const [prioridadeAberto, setPrioridadeAberto] = useState(false);
  const [githubMenuAberto, setGithubMenuAberto] = useState(false);
  const [githubUrlTemp, setGithubUrlTemp] = useState('');
  const [mergeAberto, setMergeAberto] = useState(false);
  const [organizando, setOrganizando] = useState(false);

  // Etapas minimizadas ficam no navegador de cada pessoa, por card: é
  // preferência de leitura, não dado do card — não faz sentido a minimização
  // de um vazar pro outro nem ocupar tabela no servidor.
  const chaveColapso = card?.id ? `kyndo_etapas_colapsadas_${card.id}` : null;
  const [colapsadas, setColapsadas] = useState(() => {
    if (!chaveColapso) return {};
    try {
      return JSON.parse(localStorage.getItem(chaveColapso) || '{}');
    } catch {
      return {};  // storage bloqueado ou JSON corrompido não pode derrubar o modal
    }
  });

  // Ao contrário da minimização (que é por card), ocultar concluídas é jeito
  // de ler: quem gosta, gosta em todo card. Por isso é uma chave só, global.
  const CHAVE_OCULTAR = 'kyndo_ocultar_etapas_concluidas';
  const [ocultarConcluidas, setOcultarConcluidas] = useState(() => {
    try {
      return localStorage.getItem(CHAVE_OCULTAR) === '1';
    } catch {
      return false;
    }
  });

  const alternarOcultarConcluidas = () => {
    setOcultarConcluidas(prev => {
      const proximo = !prev;
      try {
        localStorage.setItem(CHAVE_OCULTAR, proximo ? '1' : '0');
      } catch { /* storage bloqueado: vale só nesta sessão */ }
      return proximo;
    });
  };

  const alternarColapso = (itemId) => {
    setColapsadas(prev => {
      const proximo = { ...prev, [itemId]: !prev[itemId] };
      if (!proximo[itemId]) delete proximo[itemId];
      try {
        if (chaveColapso) localStorage.setItem(chaveColapso, JSON.stringify(proximo));
      } catch { /* modo privado / storage cheio: minimiza só nesta sessão */ }
      return proximo;
    });
  };

  const definirColapsoDeTodas = (colapsar) => {
    const proximo = colapsar
      ? Object.fromEntries(checklist.filter(i => (i.subetapas || []).length > 0).map(i => [i.id, true]))
      : {};
    setColapsadas(proximo);
    try {
      if (chaveColapso) localStorage.setItem(chaveColapso, JSON.stringify(proximo));
    } catch { /* idem */ }
  };
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
  // Fundir apaga um card inteiro e mexe em sete tabelas — fica no cargo mais
  // forte do sistema, não numa permissão de cargo. O backend revalida.
  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin';
  const podeFundir = isAdmin && card?.id && (allCards || []).some(c => c.id !== card.id);

  // Preserved exactly as before RBAC: authors keep self-service editing rights
  // in public columns / on their own new card, on top of whatever their cargos grant.
  const podeEditarDescricao = canEditCard || (col?.publica && (isAuthor || !card?.id));
  const podeDeletar = card?.id && (canDeleteCard || (isAuthor && col?.id === 'col-1'));
  const mostrarPrioridade = canEditPrioridade || prioridade !== 'Normal' || col?.id !== 'col-1';
  const mostrarPrazo = canEditPrazo || prazo;
  const mostrarEtapas = canCompleteEtapas || (checklist.length > 0 && hasPermission(user, 'ver_etapas'));

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

  const temSubetapas = checklist.some(i => (i.subetapas || []).length > 0);

  // Uma etapa concluída sai inteira; uma etapa em aberto fica, mas perde as
  // sub-etapas já feitas. No modo Editar nada é ocultado — não se organiza o
  // que não está na tela. A porcentagem segue contando tudo, oculto incluído,
  // porque ela é progresso real, não o que está visível.
  const ocultando = ocultarConcluidas && !organizando;
  const checklistVisivel = ocultando
    ? checklist
        .filter(i => !i.concluido)
        .map(i => ({ ...i, subetapas: (i.subetapas || []).filter(s => !s.concluido) }))
    : checklist;

  const ocultasEtapas = checklist.filter(i => i.concluido).length;
  const ocultasSubetapas = checklist
    .filter(i => !i.concluido)
    .reduce((acc, i) => acc + (i.subetapas || []).filter(s => s.concluido).length, 0);
  const totalOcultas = ocultasEtapas + ocultasSubetapas;

  // Abre/fecha o painel de observações da etapa e, ao abrir, marca a
  // observação como vista. Extraído porque tanto o chevron quanto o losango
  // de "tem observação" disparam a mesma coisa.
  const alternarObservacoes = (item) => {
    const abrindo = expandedItemId !== item.id;
    setExpandedItemId(abrindo ? item.id : null);
    setNovaSubetapa('');
    if (abrindo && item.notas_nao_vista && card?.id) {
      authFetch(`${API}/cards/${card.id}/items/${item.id}/seen`, { method: 'POST' });
      setChecklist(cl => cl.map(i => i.id === item.id ? { ...i, notas_nao_vista: false } : i));
    }
  };

  const percentual = checklist.length > 0 ? Math.round(
    checklist.reduce((acc, item) => {
      const subs = item.subetapas || [];
      return acc + (subs.length === 0 ? (item.concluido ? 1 : 0) : subs.filter(s => s.concluido).length / subs.length);
    }, 0) / checklist.length * 100
  ) : 0;

  // Resolve true se o servidor aceitou (o App já fecha o card nesse caso).
  const salvar = async () => {
    setSalvando(true);
    try {
      return await onSave({ ...card, titulo, descricao: desc, checklist, prioridade, comentarios, prazo, autor: card?.autor || user.nome, responsaveis, github_url: githubUrl, recorrente, recorrencia_dias: recorrente ? recorrenciaDias : null });
    } finally {
      setSalvando(false);
    }
  };

  // Toda saída do card passa por aqui: com alteração pendente, pergunta antes.
  const sairOu = (acao) => (temAlteracoes ? setSaidaPendente(() => acao) : acao());

  const salvarESair = async () => {
    const acao = saidaPendente;
    if (await salvar()) { setSaidaPendente(null); acao(); }
  };

  // O voltar do navegador e o fechar/recarregar a aba saem sem passar pelos
  // botões daqui — o App consulta esta guarda e o navegador mostra o aviso dele.
  useEffect(() => {
    if (!temAlteracoes) return;
    if (guardaSaidaRef) guardaSaidaRef.current = (acao) => setSaidaPendente(() => acao);
    const aviso = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', aviso);
    return () => {
      if (guardaSaidaRef) guardaSaidaRef.current = null;
      window.removeEventListener('beforeunload', aviso);
    };
  }, [temAlteracoes, guardaSaidaRef]);

  return (
    // Tela própria do card: cobre o quadro inteiro (o cabeçalho do app fica
    // em z-110). Voltar do navegador fecha, como antes — o App já põe o card
    // aberto no histórico.
    <div className="fixed inset-0 z-[200] bg-slate-950 flex flex-col">
      <div className="shrink-0 flex items-center gap-2 md:gap-3 px-3 md:px-8 py-3 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md">
        <button onClick={() => sairOu(onClose)} className="flex items-center gap-1.5 px-2.5 md:px-3 py-2 rounded-lg text-xs md:text-sm font-bold text-slate-300 hover:bg-slate-800 transition-colors">
          <ArrowLeft size={16}/> <span className="hidden sm:inline">Voltar</span>
        </button>
        {col && (
          <span className="flex items-center gap-1.5 text-[10px] md:text-xs font-bold uppercase tracking-widest text-slate-400 min-w-0">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: col.cor || '#64748b' }}/>
            <span className="truncate">{col.titulo}</span>
          </span>
        )}
        <div className="flex-1"/>
        {temAlteracoes && <span className="hidden sm:inline text-[11px] font-bold text-amber-300/80">Alterações não salvas</span>}
        <button onClick={salvar} disabled={salvando} className="px-4 md:px-6 py-2 bg-emerald-600 text-white rounded-lg font-bold text-xs md:text-sm shadow-lg hover:bg-emerald-700 disabled:opacity-60 transition-colors">{salvando ? 'Salvando...' : 'Salvar Tudo'}</button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {/* No celular vale a ordem do DOM: título, barra lateral (detalhes e
            cronômetro primeiro), depois o conteúdo. Do lg pra cima o grid põe
            a barra lateral à direita do conteúdo. */}
        <div className="max-w-7xl mx-auto px-3 md:px-8 py-5 md:py-8 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px] gap-5 lg:gap-x-8 items-start">
          <input disabled={!podeEditarDescricao} value={titulo} onChange={e => setTitulo(e.target.value)}
            className={`lg:col-span-2 text-2xl md:text-3xl font-black w-full outline-none bg-transparent ${!podeEditarDescricao ? 'text-slate-300' : 'text-slate-100'}`}
            placeholder="Título da demanda..."/>

          <aside className="lg:col-start-2 lg:row-start-2 space-y-5 min-w-0">
            <div className={`${PAINEL} space-y-4`}>
              {mostrarPrioridade && (
                <Campo rotulo="Prioridade">
                  {canEditPrioridade ? (
                    <div className="relative">
                      <button onClick={() => setPrioridadeAberto(!prioridadeAberto)} className={`flex items-center gap-1 text-xs font-bold uppercase rounded-lg px-2.5 py-1.5 outline-none cursor-pointer transition-colors ${PRIORIDADES_BADGE[prioridade]}`}>
                        {prioridade} <ChevronDown size={12}/>
                      </button>
                      {prioridadeAberto && (
                        <>
                          <div className="fixed inset-0 z-[210]" onClick={() => setPrioridadeAberto(false)}/>
                          <div className="absolute top-full mt-1 left-0 w-32 bg-slate-800 rounded-xl shadow-xl border border-slate-700 z-[220] overflow-hidden animate-in fade-in zoom-in-95">
                            {['Baixa', 'Normal', 'Alta', 'Urgente'].map(prio => (
                              <div key={prio} onClick={() => { setPrioridade(prio); setPrioridadeAberto(false); }} className={`p-2 px-3 hover:bg-slate-700 cursor-pointer flex items-center transition-colors ${prioridade === prio ? 'bg-slate-700/60' : ''}`}>
                                <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded w-full text-center ${PRIORIDADES_BADGE[prio]}`}>{prio}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <span className={`inline-block text-xs font-bold uppercase rounded-lg px-2.5 py-1.5 ${PRIORIDADES_BADGE[prioridade]}`}>{prioridade}</span>
                  )}
                </Campo>
              )}

              {mostrarPrazo && (
                <Campo rotulo="Prazo">
                  <div className="inline-flex items-center gap-1.5 bg-slate-800 border border-slate-700 px-2.5 py-1.5 rounded-lg text-sm text-slate-300">
                    <Calendar size={14} className="text-orange-400"/>
                    {canEditPrazo ? (
                      <input type="date" value={prazo} onChange={e => setPrazo(e.target.value)} className="bg-transparent outline-none cursor-pointer text-slate-100 [color-scheme:dark]"/>
                    ) : (
                      <span className="font-bold text-slate-100">{formatarData(prazo)}</span>
                    )}
                  </div>
                </Campo>
              )}

              <Campo rotulo="Responsáveis">
                <div className="flex flex-wrap items-center gap-1.5">
                  {responsaveis.map(nome => (
                    <span key={nome} className={`flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full ${userColor(nome)}`}>
                      {nome}
                      {canManageResponsaveis && responsaveis.length > 1 && (
                        <button onClick={e => { e.stopPropagation(); setResponsaveis(responsaveis.filter(r => r !== nome)); }} className="hover:text-red-500 leading-none">×</button>
                      )}
                    </span>
                  ))}
                  {canManageResponsaveis && (
                    <select value="" onChange={e => { if (e.target.value && !responsaveis.includes(e.target.value)) setResponsaveis([...responsaveis, e.target.value]); }} className="text-[11px] font-bold border border-dashed border-slate-600 rounded-full px-2 py-0.5 outline-none bg-transparent text-slate-400 cursor-pointer">
                      <option value="">+ add</option>
                      {(allUsers || []).filter(u => !responsaveis.includes(u.nome)).map(u => <option key={u.id} value={u.nome}>{u.nome}</option>)}
                    </select>
                  )}
                </div>
              </Campo>

              <Campo rotulo="GitHub">
                <div className="relative flex items-center gap-1.5">
                  {githubUrl ? (
                    <a href={githubUrl} target="_blank" rel="noopener noreferrer" title="Abrir no GitHub" className="flex-1 min-w-0 flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 hover:border-slate-500 transition-colors">
                      <GitHubIcon size={16}/> <span className="truncate">{githubUrl.replace(/^https?:\/\/(www\.)?github\.com\//i, '')}</span>
                    </a>
                  ) : (
                    <span className="flex-1 text-xs text-slate-500">Sem link</span>
                  )}
                  <button onClick={() => { setGithubUrlTemp(githubUrl); setGithubMenuAberto(true); }} title="Configurar link do GitHub" className="flex items-center justify-center w-8 h-8 shrink-0 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors">
                    <MoreHorizontal size={16}/>
                  </button>
                  {githubMenuAberto && (
                    <>
                      <div className="fixed inset-0 z-[210]" onClick={() => setGithubMenuAberto(false)}/>
                      {/* right-0: o botão fica na borda direita da barra lateral. */}
                      <div className="absolute top-full mt-1 right-0 w-64 bg-slate-800 rounded-xl shadow-xl border border-slate-700 z-[220] p-3 animate-in fade-in zoom-in-95">
                        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Link do GitHub</p>
                        <p className="text-[10px] text-slate-500 leading-relaxed mb-2">
                          Repositório mostra os commits recentes; pull request mostra o estado dela e os commits dela.
                        </p>
                        <div className="flex gap-1.5">
                          <input autoFocus type="text" value={githubUrlTemp} onChange={e => setGithubUrlTemp(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') { setGithubUrl(normalizeGithubUrl(githubUrlTemp)); setGithubMenuAberto(false); } if (e.key === 'Escape') setGithubMenuAberto(false); }}
                            placeholder="github.com/dono/repo ou .../pull/123" className="flex-1 text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
                          <button onClick={() => { setGithubUrl(normalizeGithubUrl(githubUrlTemp)); setGithubMenuAberto(false); }} className="px-2 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors">OK</button>
                        </div>
                        {/* O OK só mexe em estado local — sem esse aviso a pessoa
                            fecha o card achando que salvou, e nada persiste. */}
                        <p className="text-[10px] text-amber-400/80 mt-1.5 leading-relaxed">
                          O OK não salva: precisa clicar em <span className="font-bold">Salvar Tudo</span> no card depois.
                        </p>
                        {githubUrl && (
                          <button onClick={() => { setGithubUrl(''); setGithubUrlTemp(''); setGithubMenuAberto(false); }} className="mt-2 text-[10px] text-red-400 hover:text-red-300 font-bold">Remover link</button>
                        )}
                        {podeFundir && (
                          <>
                            <div className="border-t border-slate-700 my-3"/>
                            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Administração</p>
                            <button
                              onClick={() => { setGithubMenuAberto(false); setMergeAberto(true); }}
                              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-amber-300 hover:bg-amber-500/10 transition-colors text-xs font-bold"
                            >
                              <Merge size={14}/> Fundir com outro cartão
                            </button>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </Campo>

              {canManageEtapas && (
                <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 space-y-2">
                  <label className="flex items-center gap-2 text-xs font-bold text-slate-300 cursor-pointer">
                    <input type="checkbox" checked={recorrente} onChange={e => setRecorrente(e.target.checked)}/>
                    <Repeat size={14} className="text-slate-500"/> Tarefa recorrente
                  </label>
                  {recorrente && (
                    <div className="flex flex-wrap items-center gap-2 pl-6">
                      <select
                        value={recorrenciaPreset}
                        onChange={e => {
                          const v = e.target.value;
                          setRecorrenciaPreset(v === 'custom' ? 'custom' : Number(v));
                          if (v !== 'custom') setRecorrenciaDias(Number(v));
                        }}
                        className="text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"
                      >
                        <option value={1}>Diária</option>
                        <option value={7}>Semanal</option>
                        <option value={15}>Quinzenal</option>
                        <option value={30}>Mensal</option>
                        <option value="custom">Personalizado</option>
                      </select>
                      {recorrenciaPreset === 'custom' && (
                        <span className="flex items-center gap-1 text-xs text-slate-400">
                          a cada
                          <input type="number" min="1" value={recorrenciaDias} onChange={e => setRecorrenciaDias(Math.max(1, Number(e.target.value) || 1))} className="w-16 text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"/>
                          dia(s)
                        </span>
                      )}
                      {card?.recorrente && card?.recorrencia_proximo_reset && (
                        <span className="text-[10px] text-slate-500">
                          Próximo reinício: {formatarData(card.recorrencia_proximo_reset.slice(0, 10))} — volta para "{allColumns?.find(c => c.id === card.recorrencia_coluna_reset)?.titulo || card.recorrencia_coluna_reset}"
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {card?.data_criacao && (
                <div className="text-[11px] text-slate-500 pt-3 border-t border-slate-800">
                  Criado em {card.data_criacao}{card.autor ? <> por <span className="font-bold text-slate-400">{card.autor}</span></> : null}
                </div>
              )}
            </div>

            {card?.id && (
              <div className={PAINEL}>
                <TempoSection
                  cardId={card.id}
                  usuario={user.nome}
                  // A etapa escolhida precisa existir no servidor — etapa recém-criada
                  // e ainda não salva não aparece até o "Salvar Tudo".
                  checklistSalvo={card.checklist}
                  mostrarEtapas={mostrarEtapas}
                  cronometro={cronometro}
                  onCronometroChange={onCronometroChange}
                />
              </div>
            )}

            {card?.id && (
              <div className={`${PAINEL} space-y-5`}>
                <GithubPrSection cardId={card.id}/>
                <AttachmentsSection cardId={card.id} user={user} canManage={canEditCard}/>
              </div>
            )}
          </aside>

          <main className="lg:col-start-1 lg:row-start-2 space-y-6 md:space-y-8 min-w-0">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-slate-300 font-bold text-sm"><AlignLeft size={16}/> Descrição</div>
              {podeEditarDescricao ? (
                <textarea value={desc} onChange={handleDescChange} onKeyDown={handleDescKeyDown} className="w-full h-40 md:h-56 p-3 md:p-4 bg-slate-900 text-slate-100 rounded-xl border border-slate-800 outline-none focus:border-emerald-500 text-sm font-mono shadow-inner resize-y" placeholder="Dica: Use '- ' para criar listas..."/>
              ) : (
                <div className="w-full min-h-[6rem] p-3 md:p-4 bg-slate-900 rounded-xl border border-slate-800 text-sm font-mono text-slate-200 shadow-inner whitespace-pre-wrap break-words">
                  {desc ? renderTextWithLinks(desc) : <span className="text-slate-500">Apenas visualização.</span>}
                </div>
              )}
            </div>

            {mostrarEtapas && (
              <div className={`${PAINEL} space-y-4`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-slate-300 font-bold text-sm shrink-0"><CheckSquare size={16}/> Etapas</div>
                  <div className="flex items-center gap-1 min-w-0">
                    {!organizando && checklist.some(i => i.concluido || (i.subetapas || []).some(s => s.concluido)) && (
                      <button onClick={alternarOcultarConcluidas}
                        title={ocultarConcluidas ? 'Mostrar etapas concluídas' : 'Ocultar etapas concluídas'}
                        className={`p-1 rounded-lg transition-colors ${ocultarConcluidas ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-500 hover:text-slate-200 hover:bg-slate-800'}`}>
                        {ocultarConcluidas ? <EyeOff size={13}/> : <Eye size={13}/>}
                      </button>
                    )}
                    {temSubetapas && !organizando && (
                      <>
                        <button onClick={() => definirColapsoDeTodas(true)} title="Minimizar todas"
                          className="p-1 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors">
                          <Minus size={13}/>
                        </button>
                        <button onClick={() => definirColapsoDeTodas(false)} title="Expandir todas"
                          className="p-1 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors">
                          <Plus size={13}/>
                        </button>
                      </>
                    )}
                    {canManageEtapas && !organizando && checklist.length > 0 && (
                      <button onClick={() => setOrganizando(true)} title="Reordenar, indentar, renomear e excluir etapas"
                        className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold text-slate-400 hover:text-emerald-400 hover:bg-slate-800 transition-colors">
                        <ListTree size={13}/> Editar
                      </button>
                    )}
                    {checklist.length > 0 && <span className="text-sm font-bold text-slate-400 ml-1 shrink-0">{percentual}%</span>}
                  </div>
                </div>
                {checklist.length > 0 && <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden"><div className={`h-full transition-all duration-300 ${percentual === 100 ? 'bg-emerald-500' : 'bg-teal-500'}`} style={{ width: `${percentual}%` }}/></div>}
                {organizando ? (
                  <EtapasEditor
                    checklist={checklist}
                    novoId={novoId}
                    usuario={user.nome}
                    onCancelar={() => setOrganizando(false)}
                    onAplicar={nova => { setChecklist(nova); setOrganizando(false); }}
                  />
                ) : (
                <div className="space-y-1">
                  {checklistVisivel.map(item => {
                    // `item` pode estar filtrado (sub-etapas concluídas
                    // removidas). O contador da linha minimizada tem que sair
                    // do item COMPLETO, senão ele mostra "0/3" pra uma etapa
                    // que na verdade tem 2 de 5 prontas.
                    const itemCompleto = checklist.find(i => i.id === item.id) || item;
                    const subetapas = item.subetapas || [];
                    const subetapasTotais = itemCompleto.subetapas || [];
                    const isExpanded = expandedItemId === item.id;
                    const colapsada = !!colapsadas[item.id];
                    const concluidasSub = subetapasTotais.filter(s => s.concluido).length;
                    const temObservacao = !!(item.notas || '').trim();
                    return (
                      <div key={item.id} id={`etapa-${item.id}`} className="mb-1">
                        <div className="flex items-center gap-2 group/item">
                          {/* Dobrar as filhas. Só aparece quando existem — e é
                              separado do chevron da direita, que abre as
                              observações, pra não virar dois botões iguais. */}
                          {subetapas.length > 0 ? (
                            <button onClick={() => alternarColapso(item.id)}
                              title={colapsada ? 'Expandir sub-etapas' : 'Minimizar sub-etapas'}
                              className="shrink-0 -ml-1 p-0.5 text-slate-500 hover:text-emerald-400 transition-colors">
                              {colapsada ? <ChevronRight size={13}/> : <ChevronDown size={13}/>}
                            </button>
                          ) : (
                            <span className="shrink-0 -ml-1 w-[21px]"/>
                          )}
                          <button disabled={!canCompleteEtapas} onClick={() => { const nowDone = !item.concluido; setChecklist(checklist.map(i => i.id === item.id ? { ...i, concluido: nowDone, concluidoPor: nowDone ? user.nome : null, subetapas: nowDone ? (i.subetapas||[]).map(s => ({...s, concluido: true, concluidoPor: user.nome})) : (i.subetapas||[]) } : i)); }} className={`${!canCompleteEtapas ? 'cursor-default' : 'cursor-pointer hover:scale-110 transition-transform'} shrink-0`}>
                            {item.concluido ? <CheckCircle2 size={16} className="text-emerald-500"/> : <Circle size={16} className="text-slate-600"/>}
                          </button>
                          {canManageEtapas && editingItemId === item.id ? (
                            <input value={editingItemText} onChange={e => setEditingItemText(e.target.value)} onBlur={() => { if (editingItemText.trim()) setChecklist(checklist.map(i => i.id === item.id ? {...i, texto: editingItemText.trim()} : i)); setEditingItemId(null); }} onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') setEditingItemId(null); }} className="flex-1 min-w-0 text-sm border-b-2 border-emerald-400 outline-none bg-transparent text-slate-200 py-0.5" autoFocus/>
                          ) : (
                            <span className={`flex-1 min-w-0 text-sm ${item.concluido ? 'text-slate-500 line-through' : 'text-slate-200'} ${canManageEtapas ? 'cursor-pointer hover:text-emerald-400' : ''}`} onClick={() => { if (canManageEtapas) { setEditingItemId(item.id); setEditingItemText(item.texto); } }}>{item.texto}</span>
                          )}
                          <div className="flex items-center gap-1 shrink-0">
                            {/* Escondeu as filhas: mostra quantas e quantas
                                estão prontas, senão minimizar cega você. */}
                            {colapsada && (
                              <button onClick={() => alternarColapso(item.id)} title="Expandir sub-etapas"
                                className="text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap bg-slate-800 text-slate-400 hover:text-emerald-400 transition-colors">
                                {concluidasSub}/{subetapasTotais.length}
                              </button>
                            )}
                            {item.concluido && item.concluidoPor && item.concluidoPor === item.criador
                              ? <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(item.concluidoPor)}`}>✓ {item.concluidoPor}</span>
                              : <>{item.criador && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ${userColor(item.criador)}`}>{item.criador}</span>}{item.concluido && item.concluidoPor && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(item.concluidoPor)}`}>✓ {item.concluidoPor}</span>}</>}
                            {/* Excluir vive só no modo Editar: aqui um X ao
                                lado da caixa de concluir é clique errado
                                fácil de dar, e etapa apagada não volta. */}
                            {temObservacao && (
                              <button onClick={() => alternarObservacoes(item)}
                                title="Esta etapa tem observações"
                                className={`text-[11px] leading-none px-0.5 transition-colors ${isExpanded ? 'text-amber-300' : 'text-amber-400 hover:text-amber-300'}`}>
                                ◆
                              </button>
                            )}
                            <button onClick={() => alternarObservacoes(item)} className="relative p-0.5 text-slate-500 hover:text-emerald-400 transition-colors">
                              {item.notas_nao_vista && !isExpanded && (
                                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-red-500 rounded-full ring-1 ring-slate-900 animate-pulse" title="Nova observação nesta etapa"/>
                              )}
                              {isExpanded ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}
                            </button>
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="ml-7 mt-1 mb-2 pl-3 border-l-2 border-emerald-700 space-y-2">
                            <textarea value={item.notas || ''} onChange={e => setChecklist(checklist.map(i => i.id === item.id ? {...i, notas: e.target.value} : i))} disabled={!canManageEtapas} placeholder={canManageEtapas ? 'Observações...' : 'Sem observações.'} className="w-full h-20 p-2 bg-slate-800 text-slate-100 rounded-lg border border-slate-700 outline-none focus:border-emerald-500 text-sm resize-none"/>
                            {canManageEtapas && (
                              <div className="flex gap-2">
                                <input value={novaSubetapa} onChange={e => setNovaSubetapa(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && novaSubetapa.trim()) { setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: [...(i.subetapas||[]), {id: novoId('sub'), texto: novaSubetapa.trim(), concluido: false, criador: user.nome}]} : i)); setNovaSubetapa(''); } }} className="flex-1 p-1.5 bg-slate-800 text-slate-100 border border-slate-700 rounded text-xs outline-none focus:border-emerald-400" placeholder="Adicionar sub-etapa..."/>
                                <button onClick={() => { if (!novaSubetapa.trim()) return; setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: [...(i.subetapas||[]), {id: novoId('sub'), texto: novaSubetapa.trim(), concluido: false, criador: user.nome}]} : i)); setNovaSubetapa(''); }} className="px-3 py-1.5 bg-emerald-600 text-white rounded text-xs font-bold">Add</button>
                              </div>
                            )}
                          </div>
                        )}
                        {subetapas.length > 0 && !colapsada && (
                          <div className="ml-7 pl-3 mt-1 border-l-2 border-slate-700 space-y-1">
                            {subetapas.map(sub => (
                              <div key={sub.id} className="flex items-center gap-2 group/sub">
                                <button disabled={!canCompleteEtapas} onClick={() => setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: (i.subetapas||[]).map(s => s.id === sub.id ? {...s, concluido: !s.concluido, concluidoPor: !s.concluido ? user.nome : null} : s)} : i))} className={`shrink-0 ${!canCompleteEtapas ? 'cursor-default' : 'cursor-pointer hover:scale-110 transition-transform'}`}>
                                  {sub.concluido ? <CheckCircle2 size={16} className="text-emerald-500"/> : <Circle size={16} className="text-slate-600"/>}
                                </button>
                                {canManageEtapas && editingSubItemId === sub.id ? (
                                  <input value={editingSubItemText} onChange={e => setEditingSubItemText(e.target.value)} onBlur={() => { if (editingSubItemText.trim()) setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: (i.subetapas||[]).map(s => s.id === sub.id ? {...s, texto: editingSubItemText.trim()} : s)} : i)); setEditingSubItemId(null); }} onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') setEditingSubItemId(null); }} className="flex-1 min-w-0 text-sm border-b border-emerald-400 outline-none bg-transparent text-slate-200 py-0.5" autoFocus/>
                                ) : (
                                  <span className={`flex-1 min-w-0 text-sm ${sub.concluido ? 'text-slate-500 line-through' : 'text-slate-300'} ${canManageEtapas ? 'cursor-pointer hover:text-emerald-400' : ''}`} onClick={() => { if (canManageEtapas) { setEditingSubItemId(sub.id); setEditingSubItemText(sub.texto); } }}>{sub.texto}</span>
                                )}
                                <div className="flex items-center gap-1 shrink-0">
                                  {sub.concluido && sub.concluidoPor && sub.concluidoPor === sub.criador
                                    ? <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(sub.concluidoPor)}`}>✓ {sub.concluidoPor}</span>
                                    : <>{sub.criador && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ${userColor(sub.criador)}`}>{sub.criador}</span>}{sub.concluido && sub.concluidoPor && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(sub.concluidoPor)}`}>✓ {sub.concluidoPor}</span>}</>}
                                  {/* Idem: sub-etapa também só se exclui no modo Editar. */}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {/* Estado escondido tem que se anunciar, senão você olha uma
                      lista curta e acha que perdeu etapa. */}
                  {ocultando && totalOcultas > 0 && (
                    <button onClick={alternarOcultarConcluidas}
                      className="w-full flex items-center justify-center gap-1.5 mt-2 py-1.5 rounded-lg text-[10px] font-bold text-slate-500 hover:text-emerald-400 hover:bg-slate-800/60 transition-colors">
                      <Eye size={12}/>
                      {ocultasEtapas > 0 && `${ocultasEtapas} etapa${ocultasEtapas !== 1 ? 's' : ''}`}
                      {ocultasEtapas > 0 && ocultasSubetapas > 0 && ' e '}
                      {ocultasSubetapas > 0 && `${ocultasSubetapas} sub-etapa${ocultasSubetapas !== 1 ? 's' : ''}`}
                      {' '}concluída{totalOcultas !== 1 ? 's' : ''} oculta{totalOcultas !== 1 ? 's' : ''} · mostrar
                    </button>
                  )}
                </div>
                )}
                {canManageEtapas && !organizando && (
                  <div className="flex flex-row items-center gap-2 pt-2 w-full">
                    <input value={novaSubtarefa} onChange={e => setNovaSubtarefa(e.target.value)} onKeyDown={e => e.key === 'Enter' && addSubtarefa()} className="flex-grow min-w-0 p-2 bg-slate-800 text-slate-100 border border-slate-700 rounded-lg text-sm outline-none focus:border-emerald-400" placeholder="Adicionar etapa..."/>
                    <button onClick={addSubtarefa} className="shrink-0 px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-bold shadow-md">Add</button>
                  </div>
                )}
              </div>
            )}

            {(linkedNotes.length > 0 || linkedDrawings.length > 0) && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-slate-300 font-bold text-sm"><FileText size={16}/> Notas e Desenhos vinculados</div>
                <div className="flex flex-wrap gap-2">
                  {linkedNotes.map(n => (
                    <button key={n.id} onClick={() => sairOu(() => onOpenLinkedItem?.('nota', n.id))}
                      className="flex flex-col gap-1.5 p-2 w-36 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-200 transition-colors">
                      <div className="w-32 h-32 rounded bg-slate-900 border border-slate-700 p-2 overflow-hidden">
                        {n.tipo === 'canvas' ? (
                          <div className="w-full h-full flex items-center justify-center">
                            <Network size={36} className="text-blue-400"/>
                          </div>
                        ) : (
                          <p className="text-[10px] text-slate-400 leading-snug line-clamp-6 whitespace-pre-wrap break-words text-left">
                            {n.conteudo || 'Nota vazia'}
                          </p>
                        )}
                      </div>
                      <span className="flex items-center gap-1 text-xs font-bold truncate">
                        <FileText size={12} className="text-emerald-500 shrink-0"/> <span className="truncate">{n.titulo || 'Sem título'}</span> <ExternalLink size={11} className="text-slate-500 shrink-0"/>
                      </span>
                    </button>
                  ))}
                  {linkedDrawings.map(d => (
                    <button key={d.id} onClick={() => sairOu(() => onOpenLinkedItem?.('desenho', d.id))}
                      className="flex flex-col gap-1.5 p-2 w-36 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-200 transition-colors">
                      {d.data ? (
                        <DrawingThumbnail src={d.data} size={128}/>
                      ) : (
                        <div className="w-32 h-32 flex items-center justify-center rounded" style={{ background: '#0f172a' }}>
                          <PenLine size={20} className="text-emerald-400"/>
                        </div>
                      )}
                      <span className="flex items-center gap-1 text-xs font-bold truncate">
                        <span className="truncate">{d.titulo || 'Sem título'}</span> <ExternalLink size={11} className="text-slate-500 shrink-0"/>
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
                  onNavigateToCard={(id) => sairOu(() => onNavigateToCard(id))}
                  onNavigateToEtapa={(itemId) => {
                    setExpandedItemId(itemId);
                    setTimeout(() => document.getElementById(`etapa-${itemId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 0);
                  }}
                />
                <hr className="border-slate-800"/>
              </>
            )}

            <div className="space-y-4">
              <div className="flex items-center gap-2 text-slate-300 font-bold text-sm"><MessageSquare size={16}/> Comentários</div>
              <div className="space-y-3">
                {comentarios.map(msg => {
                  const roleChips = autorRoleChips(msg.autor, allUsers);
                  const isAuthorComment = msg.autor === (card?.autor || user.nome);
                  let boxClass = 'bg-slate-800 border-slate-700';
                  if (roleChips) boxClass = 'bg-orange-500/10 border-orange-500/20';
                  else if (isAuthorComment) boxClass = 'bg-emerald-500/10 border-emerald-500/20';
                  return (
                    <div key={msg.id} className={`p-3 rounded-xl border ${boxClass}`}>
                      <div className="flex justify-between items-center mb-1">
                        <div className="flex items-center flex-wrap gap-1">
                          <span className="text-xs font-bold text-slate-100">{msg.autor}</span>
                          {roleChips || (isAuthorComment && (
                            <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Solicitante</span>
                          ))}
                        </div>
                        <span className="text-[10px] text-slate-500 font-semibold">{msg.data}</span>
                      </div>
                      <p className="text-sm text-slate-300">{msg.texto}</p>
                    </div>
                  );
                })}
              </div>
              <div className="flex flex-row gap-2 items-center mt-2 w-full">
                <textarea value={novoComentario} onChange={e => setNovoComentario(e.target.value)} className="flex-grow min-w-0 p-3 bg-slate-800 text-slate-100 border border-slate-700 rounded-xl text-sm outline-none focus:border-emerald-400 resize-none h-16 md:h-20" placeholder="Escreva um comentário..."/>
                <button onClick={addComentario} className="shrink-0 w-16 h-16 md:w-20 md:h-20 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-colors flex items-center justify-center"><Send size={18} className="ml-1"/></button>
              </div>
            </div>
          </main>
        </div>

        {/* Excluir mora longe do Salvar, pequeno e no fim da página — e ainda
            pede confirmação. */}
        {podeDeletar && (
          <div className="max-w-7xl mx-auto px-3 md:px-8 pb-8">
            <div className="border-t border-slate-800 pt-4">
              <button onClick={() => setConfirmandoExclusao(true)}
                className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] font-bold text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors">
                <Trash2 size={12}/> Excluir tarefa
              </button>
            </div>
          </div>
        )}
      </div>

      {saidaPendente && (
        <Dialogo titulo={<><AlertTriangle size={18} className="text-amber-400"/> Sair sem salvar?</>} onFechar={() => setSaidaPendente(null)}
          acoes={<>
            <button onClick={() => setSaidaPendente(null)} className="px-3 py-2 rounded-lg text-xs font-bold text-slate-300 hover:bg-slate-800 transition-colors">Continuar editando</button>
            <button onClick={() => { const acao = saidaPendente; setSaidaPendente(null); acao(); }} className="px-3 py-2 rounded-lg text-xs font-bold text-red-300 hover:bg-red-500/10 transition-colors">Sair sem salvar</button>
            <button autoFocus onClick={salvarESair} disabled={salvando} className="px-4 py-2 rounded-lg text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60 transition-colors">{salvando ? 'Salvando...' : 'Salvar e sair'}</button>
          </>}>
          Você alterou esta tarefa e ainda não salvou. Se sair agora, as alterações se perdem.
        </Dialogo>
      )}

      {confirmandoExclusao && (
        <Dialogo titulo={<><Trash2 size={18} className="text-red-400"/> Excluir esta tarefa?</>} onFechar={() => setConfirmandoExclusao(false)}
          acoes={<>
            <button autoFocus onClick={() => setConfirmandoExclusao(false)} className="px-3 py-2 rounded-lg text-xs font-bold text-slate-300 hover:bg-slate-800 transition-colors">Cancelar</button>
            <button onClick={() => { setConfirmandoExclusao(false); onDelete(card.id); }} className="px-4 py-2 rounded-lg text-xs font-bold bg-red-600 text-white hover:bg-red-700 transition-colors">Excluir tarefa</button>
          </>}>
          <span className="font-bold text-slate-200">{titulo || card?.titulo}</span> vai para a lixeira junto com as etapas, os comentários, os anexos e o tempo registrado nela. Dá para recuperar pelo log de auditoria em até 30 dias.
        </Dialogo>
      )}

      {mergeAberto && (
        <MergeCardDialog
          card={card}
          allCards={allCards}
          allColumns={allColumns}
          onCancel={() => setMergeAberto(false)}
          onMerged={resultado => { setMergeAberto(false); onMerged?.(resultado); }}
        />
      )}
    </div>
  );
}
