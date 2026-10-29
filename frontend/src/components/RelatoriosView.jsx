import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Clock, ClipboardPaste, RefreshCw, Timer, History, Send, Check, Mail, LayoutTemplate, ChevronDown, Settings2, Save, CalendarClock, Repeat, X, Inbox, FileText, MessageSquare } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { formatarData, hasPermission } from '../constants.jsx';
import { formatarDuracao } from '../cronometro.js';
import ModelosRelatorioModal from './ModelosRelatorioModal.jsx';
import ConversaRelatorio from './ConversaRelatorio.jsx';
import EnvioAutomaticoModal from './EnvioAutomaticoModal.jsx';
import RelatoriosRecebidos from './RelatoriosRecebidos.jsx';

// Datas no fuso de quem olha, no formato que o backend espera (AAAA-MM-DD).
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const somarDias = (dataIso, n) => { const d = new Date(`${dataIso}T12:00:00`); d.setDate(d.getDate() + n); return iso(d); };
const hora = (dataHoraIso) => (dataHoraIso || '').slice(11, 16);
const DIAS_SEMANA = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];

const rotuloDoDia = (dataIso) => {
  const hoje = iso(new Date());
  if (dataIso === hoje) return 'Hoje';
  if (dataIso === somarDias(hoje, -1)) return 'Ontem';
  return DIAS_SEMANA[new Date(`${dataIso}T12:00:00`).getDay()];
};

// Os cards do dia em texto: vai no "Inserir no relatório" e no campo {resumo} dos modelos.
function cardsEmTexto(atividade) {
  const linhas = [];
  for (const c of atividade.cards) {
    linhas.push(`• ${c.titulo || 'Card excluído'}${c.segundos ? ` — ${formatarDuracao(c.segundos)}` : ''}`);
    for (const e of c.etapas) if (e.texto) linhas.push(`   - ${e.texto}: ${formatarDuracao(e.segundos)}`);
    for (const a of c.acoes) {
      if (a.acao === 'etapa_concluida' || a.acao === 'subetapa_concluida') linhas.push(`   - ${a.rotulo}: ${a.detalhe}`);
    }
  }
  for (const a of atividade.atividades || []) linhas.push(`• ${a.titulo} (atividade) — ${formatarDuracao(a.segundos)}`);
  return linhas.join('\n') || '(nada registrado neste dia)';
}

// Texto que o botão "Inserir no relatório" cola no fim do que já foi escrito.
function resumoEmTexto(dataIso, atividade) {
  return `Resumo de ${formatarData(dataIso)} — ${formatarDuracao(atividade.total_segundos)} cronometradas\n${cardsEmTexto(atividade)}`;
}

// Troca os campos do modelo ({data}, {resumo}...) pelos dados do dia.
function preencherModelo(conteudo, dataIso, atividade, nome) {
  const semana = DIAS_SEMANA[new Date(`${dataIso}T12:00:00`).getDay()];
  const valores = {
    data: formatarData(dataIso),
    dia_da_semana: ['sábado', 'domingo'].includes(semana) ? semana : `${semana}-feira`,
    nome,
    tempo_total: formatarDuracao(atividade.total_segundos),
    resumo: cardsEmTexto(atividade),
  };
  return conteudo.replace(/\{(data|dia_da_semana|nome|tempo_total|resumo)\}/g, (_, campo) => valores[campo]);
}

const DIAS_CURTOS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'];
const ORIGEM = { agendado: 'agendado', automatico: 'automático' };
const dataHora = (iso) => (iso ? new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');
const paraCampo = (d) => `${iso(d)}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

// "seg a sex às 18:00 para Fulano" — o resumo do envio automático na tela.
function descreverAutomatico(a) {
  if (!a?.ativo) return 'desligado';
  const dias = [...a.dias].sort();
  const seguidos = dias.length > 2 && dias.every((d, i) => i === 0 || d === dias[i - 1] + 1);
  const quando = dias.length === 7 ? 'todo dia' : seguidos ? `${DIAS_CURTOS[dias[0]]} a ${DIAS_CURTOS[dias[dias.length - 1]]}` : dias.map(d => DIAS_CURTOS[d]).join(', ');
  return `${quando} às ${a.hora} para ${a.para_nomes.join(', ')}`;
}

const lerParaSalvos = () => { try { return JSON.parse(localStorage.getItem('kyndo_relatorio_para') || '[]'); } catch { return []; } };

// Tela "Relatórios": escrever o relatório de cada dia, com o que a pessoa fez
// naquele dia ao lado para lembrar. Salva sozinho enquanto digita e manda
// por e-mail aos gestores escolhidos (a escolha fica lembrada).
export default function RelatoriosView({ user, onAbrirCard, abrir, onAbrirUsado, onLido }) {
  const [aba, setAba] = useState(abrir?.tipo === 'recebido' ? 'recebidos' : 'meus');
  const [data, setData] = useState(() => (abrir?.tipo === 'meu' ? abrir.data : iso(new Date())));
  const [dia, setDia] = useState(null);          // resposta do servidor para `data`
  const [texto, setTexto] = useState('');
  const [salvo, setSalvo] = useState({ texto: '', em: null });
  const [estado, setEstado] = useState('ok');   // ok | salvando | erro
  const [anteriores, setAnteriores] = useState([]);
  const [gestores, setGestores] = useState(null);
  const [para, setPara] = useState(lerParaSalvos);
  const [envio, setEnvio] = useState({ enviando: false, erro: '' });
  const [modelos, setModelos] = useState([]);
  const [menuModelos, setMenuModelos] = useState(false);
  const [janelaModelos, setJanelaModelos] = useState(null);  // null | { inicial?: texto }
  const [agendando, setAgendando] = useState(null);           // null | 'AAAA-MM-DDTHH:MM' em edição
  const [automatico, setAutomatico] = useState(null);
  const [janelaAutomatico, setJanelaAutomatico] = useState(false);
  const pendente = useRef(null);                // { data, texto } ainda não gravado
  const timer = useRef(null);
  const dataAtual = useRef(data);               // respostas atrasadas de outro dia são ignoradas

  const carregarModelos = () => authFetch(`${API}/relatorios/modelos`).then(r => (r.ok ? r.json() : [])).then(setModelos);
  const carregarLista = () => authFetch(`${API}/relatorios`).then(r => (r.ok ? r.json() : [])).then(setAnteriores);

  const gravar = async (dataAlvo, conteudo) => {
    setEstado('salvando');
    const res = await authFetch(`${API}/relatorios/dia/${dataAlvo}`, { method: 'PUT', body: JSON.stringify({ conteudo }) }).catch(() => null);
    if (pendente.current?.data === dataAlvo && pendente.current?.texto === conteudo) pendente.current = null;
    if (!res?.ok) { setEstado('erro'); return; }
    const r = await res.json();
    setEstado('ok');
    if (dataAlvo === dataAtual.current) {
      setSalvo({ texto: conteudo, em: r.atualizado_em });
      atualizarEnvio(r);
    }
    carregarLista();
  };

  // Envios, conversas e agendamento vêm juntos em várias respostas do servidor.
  const atualizarEnvio = (r) => setDia(d => (d && d.data === r.data
    ? { ...d, envios: r.envios, conversas: r.conversas, agendamento: r.agendamento } : d));

  // Troca de dia: grava o que ficou pendente do dia anterior antes de buscar o novo.
  const carregarDia = async (dataAlvo) => {
    const res = await authFetch(`${API}/relatorios/dia/${dataAlvo}`);
    if (!res.ok) return;
    const r = await res.json();
    if (dataAlvo !== dataAtual.current) return;
    setDia(r);
    setTexto(r.conteudo);
    setSalvo({ texto: r.conteudo, em: r.atualizado_em });
  };

  useEffect(() => {
    dataAtual.current = data;
    clearTimeout(timer.current);
    const antes = pendente.current ? gravar(pendente.current.data, pendente.current.texto) : Promise.resolve();
    setDia(null);
    antes.then(() => carregarDia(data));
    // Respostas dos gestores chegam enquanto a tela está aberta. Só a parte
    // de envio é atualizada: o texto em edição não é tocado.
    const t = setInterval(() => {
      authFetch(`${API}/relatorios/dia/${data}`).then(res => (res.ok ? res.json() : null)).then(r => {
        if (r && r.data === dataAtual.current) { atualizarEnvio(r); if (r.conversas.some(c => c.nao_lidas)) onLido(); }
      });
    }, 30000);
    return () => clearInterval(t);
  }, [data]);

  useEffect(() => {
    onAbrirUsado();
    carregarLista();
    carregarModelos();
    authFetch(`${API}/relatorios/automatico`).then(r => (r.ok ? r.json() : null)).then(setAutomatico);
    authFetch(`${API}/relatorios/destinatarios`).then(r => (r.ok ? r.json() : [])).then(lista => {
      setGestores(lista);
      setPara(p => p.filter(id => lista.some(g => g.id === id)));
    });
  }, []);

  // Abrir o dia já marca as respostas como lidas: o pontinho do menu some.
  useEffect(() => { if (dia?.conversas?.some(c => c.nao_lidas)) onLido(); }, [dia?.data]);

  const alternarPara = (id) => setPara(p => {
    const novo = p.includes(id) ? p.filter(x => x !== id) : [...p, id];
    try { localStorage.setItem('kyndo_relatorio_para', JSON.stringify(novo)); } catch { /* sem storage: só não lembra */ }
    return novo;
  });

  const enviar = async () => {
    setEnvio({ enviando: true, erro: '' });
    // O servidor envia o texto salvo: grava antes o que ainda está pendente.
    clearTimeout(timer.current);
    if (pendente.current) await gravar(pendente.current.data, pendente.current.texto);
    const res = await authFetch(`${API}/relatorios/dia/${data}/enviar`, { method: 'POST', body: JSON.stringify({ para }) }).catch(() => null);
    const r = await res?.json().catch(() => ({}));
    if (!res?.ok) { setEnvio({ enviando: false, erro: r?.detail || 'Não foi possível enviar.' }); return; }
    setEnvio({ enviando: false, erro: '' });
    atualizarEnvio(r);
  };

  const abrirAgendamento = () => {
    const sugestao = new Date(); sugestao.setHours(18, 0, 0, 0);
    if (sugestao <= new Date()) sugestao.setTime(Date.now() + 3600000);
    setAgendando(paraCampo(sugestao));
    setEnvio({ enviando: false, erro: '' });
  };

  const agendar = async () => {
    clearTimeout(timer.current);
    if (pendente.current) await gravar(pendente.current.data, pendente.current.texto);
    const res = await authFetch(`${API}/relatorios/dia/${data}/agendamento`, {
      method: 'PUT', body: JSON.stringify({ para, enviar_em: agendando }),
    }).catch(() => null);
    const r = await res?.json().catch(() => ({}));
    if (!res?.ok) { setEnvio({ enviando: false, erro: r?.detail || 'Não foi possível agendar.' }); return; }
    setAgendando(null);
    atualizarEnvio(r);
  };

  const cancelarAgendamento = async () => {
    const res = await authFetch(`${API}/relatorios/dia/${data}/agendamento`, { method: 'DELETE' }).catch(() => null);
    if (res?.ok) atualizarEnvio(await res.json());
  };

  // Ao sair da tela, nada se perde.
  useEffect(() => () => {
    clearTimeout(timer.current);
    if (pendente.current) gravar(pendente.current.data, pendente.current.texto);
  }, []);

  const digitar = (novo) => {
    setTexto(novo);
    pendente.current = { data, texto: novo };
    clearTimeout(timer.current);
    timer.current = setTimeout(() => gravar(data, novo), 800);
  };

  const inserirResumo = () => {
    if (!dia) return;
    const resumo = resumoEmTexto(data, dia.atividade);
    digitar(texto.trim() ? `${texto.replace(/\s+$/, '')}\n\n${resumo}` : resumo);
  };

  // Modelo num dia em branco vira o texto; com texto já escrito, entra no fim.
  const usarModelo = (m) => {
    setMenuModelos(false);
    if (!dia) return;
    const preenchido = preencherModelo(m.conteudo, data, dia.atividade, user.nome);
    digitar(texto.trim() ? `${texto.replace(/\s+$/, '')}\n\n${preenchido}` : preenchido);
  };

  const ativ = dia?.atividade;
  const hoje = iso(new Date());
  const alterado = texto !== salvo.texto;

  return (
    <div className="h-full overflow-y-auto custom-scrollbar p-3 md:p-6">
      {janelaModelos && (
        <ModelosRelatorioModal modelos={modelos} inicial={janelaModelos.inicial}
          onMudou={carregarModelos} onFechar={() => setJanelaModelos(null)}/>
      )}
      {janelaAutomatico && (
        <EnvioAutomaticoModal gestores={gestores || []} onFechar={() => setJanelaAutomatico(false)}
          onSalvo={a => { setAutomatico(a); setJanelaAutomatico(false); }}/>
      )}
      <div className="max-w-6xl mx-auto space-y-4">
        {(hasPermission(user, 'acessar_gestao') || aba === 'recebidos') && (
          <div className="flex rounded-xl overflow-hidden border border-slate-700 w-fit">
            {[{ val: 'meus', label: 'Meus relatórios', Icone: FileText }, { val: 'recebidos', label: 'Recebidos', Icone: Inbox }].map(t => (
              <button key={t.val} onClick={() => setAba(t.val)}
                className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold transition-colors ${aba === t.val ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white' : 'bg-slate-900 text-slate-400 hover:text-slate-200'}`}>
                <t.Icone size={14}/> {t.label}
              </button>
            ))}
          </div>
        )}
        {aba === 'recebidos' ? (
          <RelatoriosRecebidos user={user} abrir={abrir?.tipo === 'recebido' ? abrir : null} onLido={onLido}/>
        ) : (<>
        {/* Navegação entre dias */}
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => setData(d => somarDias(d, -1))} className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700" title="Dia anterior">
            <ChevronLeft size={16}/>
          </button>
          <label className="relative flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 cursor-pointer">
            <span className="text-sm font-black text-white capitalize">{rotuloDoDia(data)}</span>
            <span className="text-sm text-slate-400">{formatarData(data)}</span>
            <input type="date" value={data} max={hoje} onChange={e => e.target.value && setData(e.target.value)}
              className="absolute inset-0 opacity-0 cursor-pointer" title="Escolher a data"/>
          </label>
          <button onClick={() => setData(d => somarDias(d, 1))} disabled={data >= hoje}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed" title="Dia seguinte">
            <ChevronRight size={16}/>
          </button>
          {data !== hoje && (
            <button onClick={() => setData(hoje)} className="px-3 py-1.5 rounded-xl text-xs font-bold text-emerald-300 hover:bg-emerald-500/10">Voltar para hoje</button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 items-start">
          {/* Relatório */}
          <section className="lg:col-span-3 bg-slate-900 border border-slate-800 rounded-2xl p-4 md:p-5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-black text-white">Relatório do dia</h2>
              <div className="flex items-center gap-3">
                <span className={`text-[11px] font-bold ${estado === 'erro' ? 'text-red-400' : 'text-slate-500'}`}>
                  {estado === 'erro' ? 'Não foi possível salvar — tente de novo'
                    : estado === 'salvando' || alterado ? 'Salvando…'
                    : salvo.em ? `Salvo às ${hora(salvo.em)}` : ''}
                </span>
                <div className="relative">
                  <button onClick={() => setMenuModelos(a => !a)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-bold">
                    <LayoutTemplate size={13}/> Modelos <ChevronDown size={12} className="text-slate-400"/>
                  </button>
                  {menuModelos && (
                    <>
                      <div className="fixed inset-0 z-40" onClick={() => setMenuModelos(false)}/>
                      <div className="absolute right-0 top-full mt-1 w-64 z-50 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl overflow-hidden">
                        {modelos.length > 0 ? (
                          <>
                            <div className="px-3 pt-2 pb-1 text-[10px] font-black text-slate-500 uppercase tracking-widest">
                              {texto.trim() ? 'Adicionar ao fim do texto' : 'Começar com'}
                            </div>
                            <div className="max-h-60 overflow-y-auto custom-scrollbar">
                              {modelos.map(m => (
                                <button key={m.id} onClick={() => usarModelo(m)} disabled={!dia}
                                  className="w-full text-left px-3 py-2 text-sm text-slate-200 hover:bg-emerald-500/10 truncate">{m.nome}</button>
                              ))}
                            </div>
                          </>
                        ) : (
                          <p className="px-3 py-2 text-xs text-slate-400">Você ainda não tem modelos.</p>
                        )}
                        <div className="h-px bg-slate-700"/>
                        <button onClick={() => { setMenuModelos(false); setJanelaModelos({ inicial: texto }); }} disabled={!texto.trim()}
                          className="w-full flex items-center gap-2 px-3 py-2 text-xs font-bold text-slate-300 hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed">
                          <Save size={13}/> Salvar o texto atual como modelo
                        </button>
                        <button onClick={() => { setMenuModelos(false); setJanelaModelos({}); }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-xs font-bold text-slate-300 hover:bg-white/5">
                          <Settings2 size={13}/> {modelos.length ? 'Criar e editar modelos' : 'Criar um modelo'}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
            <textarea value={texto} onChange={e => digitar(e.target.value)} disabled={!dia}
              placeholder="O que você fez hoje, o que ficou pendente, algum bloqueio…"
              className="w-full min-h-[320px] md:min-h-[420px] p-3 bg-slate-950 text-slate-100 border border-slate-800 rounded-xl outline-none focus:border-emerald-500 text-sm leading-relaxed resize-y"/>
            <p className="text-[11px] text-slate-500">Salva sozinho enquanto você escreve. Só você e os gestores para quem você enviar veem.</p>

            {/* Envio por e-mail */}
            <div className="pt-3 border-t border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase"><Mail size={13}/> Enviar para</div>
              <p className="text-[11px] text-slate-500 -mt-1">O gestor recebe na aba Recebidos do Kyndo e, se tiver e-mail, também por e-mail.</p>
              {gestores === null ? null : gestores.length === 0 ? (
                <p className="text-xs text-slate-500">Ninguém tem acesso à Gestão para receber relatórios. Fale com o administrador.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {gestores.map(g => {
                    const marcado = para.includes(g.id);
                    return (
                      <button key={g.id} onClick={() => alternarPara(g.id)}
                        title={g.tem_email ? 'Recebe no Kyndo e por e-mail' : `${g.nome} não tem e-mail cadastrado: recebe só no Kyndo`}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border transition-colors ${marcado
                          ? 'bg-emerald-600 border-emerald-500 text-white'
                          : 'bg-slate-950 border-slate-700 text-slate-300 hover:border-slate-500'} disabled:opacity-40 disabled:cursor-not-allowed`}>
                        {marcado && <Check size={12}/>}{g.nome}{!g.tem_email && <span className="font-normal opacity-70">(só no Kyndo)</span>}
                      </button>
                    );
                  })}
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <button onClick={enviar} disabled={envio.enviando || !texto.trim() || para.length === 0}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold disabled:opacity-40 disabled:cursor-not-allowed">
                  <Send size={14}/> {envio.enviando ? 'Enviando…' : dia?.envios?.length ? 'Enviar de novo' : 'Enviar agora'}
                </button>
                <button onClick={abrirAgendamento} disabled={para.length === 0 || agendando !== null}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-sm font-bold disabled:opacity-40 disabled:cursor-not-allowed">
                  <CalendarClock size={14}/> Agendar envio
                </button>
                {envio.erro && <span className="text-xs font-bold text-red-400">{envio.erro}</span>}
              </div>
              {agendando !== null && (
                <div className="flex flex-wrap items-center gap-2 p-2.5 rounded-xl border border-slate-700 bg-slate-950">
                  <span className="text-xs font-bold text-slate-400">Enviar em</span>
                  <input type="datetime-local" value={agendando} onChange={e => setAgendando(e.target.value)}
                    className="p-1.5 bg-slate-900 text-slate-100 border border-slate-700 rounded-lg outline-none focus:border-emerald-500 text-sm"/>
                  <button onClick={agendar} className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Agendar</button>
                  <button onClick={() => setAgendando(null)} className="text-xs font-bold text-slate-400 hover:text-slate-200">Cancelar</button>
                  <span className="w-full text-[11px] text-slate-500">Sai o texto como estiver na hora marcada, para os gestores marcados acima.</span>
                </div>
              )}
              {dia?.agendamento && (
                <div className={`flex flex-wrap items-center gap-2 text-xs ${dia.agendamento.status === 'vazio' ? 'text-amber-300' : 'text-slate-300'}`}>
                  <CalendarClock size={13}/>
                  {dia.agendamento.status === 'vazio'
                    ? <span>O envio agendado para {dataHora(dia.agendamento.enviar_em)} não saiu: o relatório estava vazio.</span>
                    : <span>Envio agendado para <b>{dataHora(dia.agendamento.enviar_em)}</b> → {dia.agendamento.para.map(p => p.nome).join(', ')}</span>}
                  <button onClick={cancelarAgendamento} className="flex items-center gap-1 font-bold text-slate-400 hover:text-red-300">
                    <X size={12}/> {dia.agendamento.status === 'vazio' ? 'Dispensar' : 'Cancelar'}
                  </button>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <Repeat size={13}/> Envio automático: <span className={automatico?.ativo ? 'font-bold text-slate-200' : ''}>{descreverAutomatico(automatico)}</span>
                <button onClick={() => setJanelaAutomatico(true)} className="font-bold text-emerald-400 hover:underline">Configurar</button>
              </div>
              {dia?.envios?.length > 0 && (
                <ul className="space-y-0.5">
                  {dia.envios.map(e => (
                    <li key={e.id} className="flex flex-wrap items-center gap-x-2 text-xs text-slate-400">
                      <Check size={12} className="text-emerald-400"/>
                      Enviado para <span className="font-bold text-slate-200">{e.para_nome}</span>
                      em {formatarData(e.enviado_em.slice(0, 10))} às {hora(e.enviado_em)}
                      {ORIGEM[e.origem] && <span className="text-slate-500">({ORIGEM[e.origem]})</span>}
                      {!e.igual_ao_atual && <span className="text-amber-300/80">· o texto mudou depois</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {dia?.conversas?.length > 0 && (
              <div className="pt-3 border-t border-slate-800 space-y-4">
                {dia.conversas.map(c => (
                  <div key={c.gestor_id} className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="flex items-center gap-1.5 text-xs font-bold text-slate-400 uppercase"><MessageSquare size={13}/> Conversa com {c.gestor_nome}</h3>
                      <span className="text-[11px] text-slate-500">{c.lido_em ? `· leu em ${dataHora(c.lido_em)}` : '· ainda não abriu'}</span>
                      {c.nao_lidas > 0 && <span className="text-[10px] font-black px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">{c.nao_lidas} nova(s)</span>}
                    </div>
                    <ConversaRelatorio autorId={user.id} data={data} gestorId={c.gestor_id} mensagens={c.mensagens}
                      onMensagens={m => setDia(d => ({ ...d, conversas: d.conversas.map(x => (x.gestor_id === c.gestor_id ? { ...x, mensagens: m } : x)) }))}
                      vazio={`${c.gestor_nome} pode responder por aqui; a resposta aparece nesta conversa.`}/>
                  </div>
                ))}
              </div>
            )}
          </section>

          <div className="lg:col-span-2 space-y-4">
            {/* O que foi feito no dia */}
            <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 md:p-5 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-base font-black text-white">O que você fez</h2>
                <button onClick={() => carregarDia(data)} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5" title="Atualizar">
                  <RefreshCw size={14}/>
                </button>
              </div>
              {!ativ ? <p className="text-sm text-slate-500">Carregando…</p> : (
                <>
                  <div className="flex items-end gap-2">
                    <Clock size={18} className="text-emerald-400 mb-1"/>
                    <span className="text-2xl font-black text-white">{formatarDuracao(ativ.total_segundos)}</span>
                    <span className="text-xs text-slate-400 mb-1">cronometradas</span>
                  </div>
                  {ativ.em_andamento && (
                    <p className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-300"><Timer size={12}/> Cronômetro ligado — o total ainda está crescendo.</p>
                  )}
                  {ativ.atividades?.length > 0 && (
                    <ul className="space-y-1.5">
                      {ativ.atividades.map(a => (
                        <li key={a.atividade_id} className="flex items-start justify-between gap-2 p-3 rounded-xl bg-violet-500/10 border border-violet-500/30">
                          <span className="text-sm font-bold text-violet-200 break-words min-w-0">
                            <span className="mr-1.5 px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300 text-[9px] font-black uppercase align-middle">atividade</span>
                            {a.titulo}
                          </span>
                          <span className="shrink-0 text-xs font-black text-violet-300">{formatarDuracao(a.segundos)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {ativ.cards.length === 0 ? (
                    !ativ.atividades?.length && <p className="text-sm text-slate-500">Nada registrado neste dia.</p>
                  ) : (
                    <ul className="space-y-2">
                      {ativ.cards.map(c => (
                        <li key={c.card_id} className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60">
                          <div className="flex items-start justify-between gap-2">
                            {c.existe ? (
                              <button onClick={() => onAbrirCard(c.card_id)} className="text-left text-sm font-bold text-slate-100 hover:text-emerald-300 hover:underline break-words min-w-0">{c.titulo}</button>
                            ) : (
                              <span className="text-sm font-bold text-slate-400 break-words min-w-0" title="Este card foi excluído">{c.titulo || 'Card excluído'}</span>
                            )}
                            {c.segundos > 0 && <span className="shrink-0 text-xs font-black text-emerald-300">{formatarDuracao(c.segundos)}</span>}
                          </div>
                          {c.etapas.some(e => e.texto) && (
                            <ul className="mt-1.5 space-y-0.5">
                              {c.etapas.map(e => (
                                <li key={e.texto ?? '__card'} className="flex justify-between gap-2 text-xs text-slate-400">
                                  <span className="truncate">{e.texto ?? 'Card inteiro (sem etapa)'}</span>
                                  <span className="shrink-0">{formatarDuracao(e.segundos)}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                          {c.acoes.length > 0 && (
                            <ul className="mt-1.5 pt-1.5 border-t border-slate-700/60 space-y-0.5">
                              {c.acoes.map((a, i) => (
                                <li key={i} className="text-xs text-slate-400 break-words">
                                  <span className="text-slate-500 font-mono mr-1.5">{hora(a.hora)}</span>
                                  <span className="text-slate-300">{a.rotulo}</span>{a.detalhe ? `: ${a.detalhe}` : ''}
                                </li>
                              ))}
                            </ul>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {(ativ.cards.length > 0 || ativ.atividades?.length > 0) && (
                    <button onClick={inserirResumo} className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">
                      <ClipboardPaste size={14}/> Inserir este resumo no relatório
                    </button>
                  )}
                </>
              )}
            </section>

            {/* Relatórios anteriores */}
            {anteriores.length > 0 && (
              <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 md:p-5 space-y-2">
                <h2 className="flex items-center gap-2 text-base font-black text-white"><History size={16} className="text-slate-400"/> Relatórios anteriores</h2>
                <ul className="max-h-72 overflow-y-auto custom-scrollbar -mx-1">
                  {anteriores.map(r => (
                    <li key={r.data}>
                      <button onClick={() => setData(r.data)}
                        className={`w-full text-left px-2 py-1.5 rounded-lg transition-colors ${r.data === data ? 'bg-emerald-500/10' : 'hover:bg-white/5'}`}>
                        <span className={`text-xs font-bold ${r.data === data ? 'text-emerald-300' : 'text-slate-200'}`}>{formatarData(r.data)}</span>
                        <span className="block text-[11px] text-slate-500 truncate">{r.resumo}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </div>
        </>)}
      </div>
    </div>
  );
}
