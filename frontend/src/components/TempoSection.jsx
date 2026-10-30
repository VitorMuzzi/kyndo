import React, { useEffect, useState } from 'react';
import { MoreHorizontal, Play, Square, Timer, Trash2 } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { userColor } from '../constants.jsx';
import { buscarCronometroAtual, formatarDuracao, formatarRelogio, iniciarCronometro, pararCronometro, segundosDesde, useAgora, useDecorrido } from '../cronometro.js';

const SEM_ETAPA = '';
const TUDO = '*';  // quem não vê etapas: um grupo só, o card inteiro

const dataHora = (iso) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

// Fim no mesmo dia do início mostra só a hora: "29/10/2026 08:01 → 08:17".
const fimDoPeriodo = (inicio, fim) => {
  const a = new Date(inicio);
  const b = new Date(fim);
  if (Number.isNaN(b.getTime())) return '';
  return a.toDateString() === b.toDateString()
    ? b.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : dataHora(fim);
};

// Etapas e sub-etapas numa lista só, na ordem do card, pra escolha e pra nome.
const listarEtapas = (checklist) => {
  const lista = [];
  for (const item of checklist || []) {
    lista.push({ id: item.id, texto: item.texto, nivel: 0 });
    for (const sub of item.subetapas || []) lista.push({ id: sub.id, texto: sub.texto, nivel: 1 });
  }
  return lista;
};

// `checklist` é o da tela, com o que ainda não foi salvo: dá pra ligar o
// cronômetro numa etapa recém-criada sem antes clicar em "Salvar Tudo".
export default function TempoSection({ cardId, usuario, checklist, mostrarEtapas, cronometro, onCronometroChange }) {
  const [dados, setDados] = useState(null);
  const [etapaEscolhida, setEtapaEscolhida] = useState('');
  const [erro, setErro] = useState('');
  const [aberta, setAberta] = useState(null);  // tarefa com o histórico de períodos aberto

  const rodandoAqui = cronometro?.card_id === cardId;
  const decorrido = useDecorrido(rodandoAqui ? cronometro : null);
  const agora = useAgora(rodandoAqui);
  const etapas = listarEtapas(checklist);
  const usaEtapas = mostrarEtapas && etapas.length > 0;
  // A etapa escolhida pode ter sido apagada da tela depois.
  const etapaValida = etapas.some(e => e.id === etapaEscolhida) ? etapaEscolhida : '';

  const carregar = () => {
    authFetch(`${API}/cards/${cardId}/tempo`)
      .then(r => (r.ok ? r.json() : null))
      .then(d => setDados(d ? { ...d, recebidoEm: Date.now() } : null));
  };

  // Recarrega quando o cronômetro liga, desliga ou troca de card.
  useEffect(carregar, [cardId, cronometro?.id]);

  const iniciar = async () => {
    setErro('');
    try {
      onCronometroChange(await iniciarCronometro(cardId, etapaValida));
    } catch (e) {
      setErro(e.message);
    }
  };

  const parar = async () => {
    setErro('');
    try {
      await pararCronometro();
      onCronometroChange(null);
    } catch (e) {
      setErro(e.message);
    }
  };

  // Mover um período próprio para outra tarefa (ou para "sem etapa").
  const moverPeriodo = async (id, itemId) => {
    setErro('');
    const res = await authFetch(`${API}/tempo/${id}`, { method: 'PUT', body: JSON.stringify({ item_id: itemId || null }) });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setErro(data.detail || 'Não foi possível mover o período.');
      return;
    }
    // O que está rodando mostra a etapa no cronômetro flutuante também.
    if (cronometro?.id === id) {
      const atual = await buscarCronometroAtual();
      if (atual !== undefined) onCronometroChange(atual);
    }
    carregar();
  };

  const apagarPeriodo = async (id) => {
    if (!window.confirm('Apagar este período de tempo?')) return;
    const res = await authFetch(`${API}/tempo/${id}`, { method: 'DELETE' });
    if (!res.ok) { setErro('Não foi possível apagar o período.'); return; }
    if (cronometro?.id === id) onCronometroChange(null);
    else carregar();
  };

  // Os totais vêm do servidor na hora da busca; o cronômetro próprio rodando
  // aqui continua somando na tela até a próxima busca.
  const extra = rodandoAqui && dados ? segundosDesde(dados, agora) : 0;
  const total = (dados?.total_segundos || 0) + extra;
  const registros = dados?.registros || [];

  // A linha de quem está com o cronômetro rodando aqui soma ao vivo, como o total.
  const porPessoa = (dados?.por_pessoa || [])
    .map(p => (p.usuario === usuario ? { ...p, segundos: p.segundos + extra } : p))
    .sort((a, b) => b.segundos - a.segundos);
  if (rodandoAqui && dados && !porPessoa.some(p => p.usuario === usuario)) porPessoa.push({ usuario, segundos: extra });
  const maxPessoa = Math.max(1, ...porPessoa.map(p => p.segundos));

  // Por tarefa: o tempo de todas as vezes que alguém trabalhou nela, somado.
  // O total por tarefa é de todo mundo; os períodos (horários) seguem a
  // mesma regra do servidor — os seus, ou de todos com ver_tempo_equipe.
  let tarefas = [];
  if (dados && total > 0) {
    if (usaEtapas) {
      const porEtapa = { ...dados.por_etapa };
      if (rodandoAqui && cronometro.item_id) porEtapa[cronometro.item_id] = (porEtapa[cronometro.item_id] || 0) + extra;
      const conhecidas = new Set(etapas.map(e => e.id));
      tarefas = [
        ...etapas.filter(e => porEtapa[e.id] > 0).map(e => ({ id: e.id, texto: e.texto, nivel: e.nivel, segundos: porEtapa[e.id] })),
        ...Object.keys(porEtapa).filter(id => !conhecidas.has(id) && porEtapa[id] > 0)
          .map(id => ({ id, texto: 'Etapa removida', nivel: 0, segundos: porEtapa[id], removida: true })),
      ];
      const semEtapa = total - Object.values(porEtapa).reduce((s, v) => s + v, 0);
      if (semEtapa > 0) tarefas.push({ id: SEM_ETAPA, texto: 'Card inteiro (sem etapa)', nivel: 0, segundos: semEtapa, semEtapa: true });
    } else {
      tarefas = [{ id: TUDO, texto: 'Card inteiro', nivel: 0, segundos: total, semEtapa: true }];
    }
  }
  const periodosDe = (tarefa) => registros
    .filter(r => tarefa.id === TUDO || (r.item_id || SEM_ETAPA) === tarefa.id)
    .sort((a, b) => a.inicio.localeCompare(b.inicio));
  const tarefaRodando = rodandoAqui ? (usaEtapas ? (cronometro.item_id || SEM_ETAPA) : TUDO) : null;
  // Etapa ainda não salva: o servidor só sabe o nome dela depois do "Salvar Tudo".
  const etapaRodando = rodandoAqui && (etapas.find(e => e.id === cronometro.item_id)?.texto || cronometro.etapa_texto);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 text-slate-300 font-bold text-sm"><Timer size={16}/> Tempo</div>
        {dados && (
          <div className="text-[11px] text-slate-400">
            Total <span className="font-bold text-slate-200">{formatarDuracao(total)}</span>
            <span className="mx-1.5 text-slate-600">·</span>
            Seu <span className="font-bold text-slate-200">{formatarDuracao(dados.meu_total_segundos + extra)}</span>
          </div>
        )}
      </div>

      {rodandoAqui ? (
        <div className="flex items-center gap-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"/>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"/>
          </span>
          <div className="flex-1 min-w-0">
            <div className="font-mono text-lg font-bold text-emerald-300 tabular-nums">{formatarRelogio(decorrido)}</div>
            {mostrarEtapas && etapaRodando && <div className="text-[11px] text-slate-400 truncate">em {etapaRodando}</div>}
          </div>
          <button onClick={parar} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/15 text-red-300 hover:bg-red-500/30 text-xs font-bold transition-colors">
            <Square size={12} fill="currentColor"/> Parar
          </button>
        </div>
      ) : (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            {usaEtapas && (
              <select value={etapaValida} onChange={e => setEtapaEscolhida(e.target.value)}
                className="flex-1 min-w-[160px] text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-2 outline-none focus:border-emerald-400">
                <option value="">Card inteiro (sem etapa)</option>
                {etapas.map(e => (
                  <option key={e.id} value={e.id}>{e.nivel === 1 ? '   ↳ ' : ''}{e.texto}</option>
                ))}
              </select>
            )}
            <button onClick={iniciar} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 text-xs font-bold transition-colors">
              <Play size={12} fill="currentColor"/> Iniciar cronômetro
            </button>
          </div>
          {cronometro && (
            <div className="text-[11px] text-amber-300/80">
              Seu cronômetro está rodando em "{cronometro.card_titulo}" — iniciar aqui encerra aquele.
            </div>
          )}
        </div>
      )}

      {erro && <div className="text-xs text-red-400">{erro}</div>}

      {tarefas.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Por tarefa</div>
          {tarefas.map(t => {
            const periodos = periodosDe(t);
            const expandida = aberta === t.id;
            return (
              <div key={t.id || 'sem-etapa'} className={`rounded-lg ${expandida ? 'bg-slate-900/60 border border-slate-700/70' : ''}`}>
                <div className="flex items-center gap-2 text-xs px-1.5 py-1">
                  {tarefaRodando === t.id && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" title="Cronômetro rodando aqui"/>}
                  <span className={`flex-1 min-w-0 truncate ${t.nivel === 1 ? 'pl-3' : ''} ${t.semEtapa || t.removida ? 'text-slate-400 italic' : 'text-slate-200'}`}>
                    {t.nivel === 1 && <span className="text-slate-600">↳ </span>}{t.texto}
                  </span>
                  <span className="font-mono text-slate-200 shrink-0">{formatarDuracao(t.segundos)}</span>
                  <button onClick={() => setAberta(expandida ? null : t.id)} disabled={periodos.length === 0}
                    title={periodos.length ? 'Ver quando foi trabalhado' : 'Sem períodos seus aqui'}
                    className={`shrink-0 p-0.5 rounded transition-colors ${expandida ? 'text-emerald-300 bg-white/10' : 'text-slate-500 hover:text-slate-200 hover:bg-white/10'} disabled:opacity-30 disabled:hover:bg-transparent`}>
                    <MoreHorizontal size={14}/>
                  </button>
                </div>
                {expandida && (
                  <div className="px-2 pb-2 pt-1 space-y-1 border-t border-slate-700/70">
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                      {dados.pode_ver_equipe ? 'Períodos trabalhados' : 'Seus períodos'} ({periodos.length})
                    </div>
                    {periodos.map(r => (
                      <div key={r.id} className="flex items-center gap-2 text-[11px] group">
                        <span className="font-mono text-slate-300 shrink-0">
                          {dataHora(r.inicio)} → {r.fim ? fimDoPeriodo(r.inicio, r.fim) : <span className="text-emerald-300">em andamento</span>}
                        </span>
                        {dados.pode_ver_equipe && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0 ${userColor(r.usuario)}`}>{r.usuario}</span>}
                        <span className="flex-1"/>
                        {r.fim && <span className="font-mono text-slate-400 shrink-0">{formatarDuracao(r.segundos)}</span>}
                        {r.meu && usaEtapas && (
                          <select value={r.item_id || ''} onChange={e => moverPeriodo(r.id, e.target.value)} title="Mover para outra tarefa"
                            className="w-24 shrink-0 text-[10px] bg-transparent text-slate-500 border border-slate-700/60 hover:border-slate-500 focus:border-emerald-400 rounded px-1 py-0.5 outline-none cursor-pointer">
                            <option value="">sem etapa</option>
                            {r.item_id && !etapas.some(e => e.id === r.item_id) && <option value={r.item_id}>Etapa removida</option>}
                            {etapas.map(e => (
                              <option key={e.id} value={e.id}>{e.nivel === 1 ? '   ↳ ' : ''}{e.texto}</option>
                            ))}
                          </select>
                        )}
                        {r.meu && (
                          <button onClick={() => apagarPeriodo(r.id)} className="shrink-0 text-slate-600 hover:text-red-400 md:opacity-0 md:group-hover:opacity-100 transition-opacity" title="Apagar período">
                            <Trash2 size={12}/>
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {porPessoa.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Por pessoa</div>
          {porPessoa.map(p => (
            <div key={p.usuario} className="flex items-center gap-2 text-xs">
              <span className={`w-24 shrink-0 truncate text-[11px] font-bold px-2 py-0.5 rounded-full ${userColor(p.usuario)}`}>{p.usuario}</span>
              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.max(4, (p.segundos / maxPessoa) * 100)}%` }}/>
              </div>
              <span className="w-16 shrink-0 text-right text-slate-300 font-mono">{formatarDuracao(p.segundos)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
