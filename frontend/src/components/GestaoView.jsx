import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, Briefcase, Check, CheckCircle2, ChevronDown, ChevronRight, Clock, RefreshCw, Search, Timer, User, Users } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { PRIORIDADES_BADGE, formatarData, userColor } from '../constants.jsx';
import { formatarDuracao, formatarRelogio, segundosDesde, useAgora } from '../cronometro.js';

// Datas no fuso de quem olha, no formato que o backend espera (AAAA-MM-DD).
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const PERIODOS = [
  { key: 'hoje', label: 'Hoje', calc: (h) => [h, h] },
  { key: 'semana', label: 'Semana', calc: (h) => { const ini = new Date(h); ini.setDate(h.getDate() - ((h.getDay() + 6) % 7)); return [ini, h]; } },
  { key: 'mes', label: 'Mês', calc: (h) => [new Date(h.getFullYear(), h.getMonth(), 1), h] },
  { key: 'personalizado', label: 'Personalizado' },
];

const FILTROS_CARDS = [
  { key: 'abertos', label: 'Em aberto', teste: c => !c.concluido },
  { key: 'atrasados', label: 'Atrasados', teste: c => c.atrasado },
  { key: 'periodo', label: 'Com horas no período', teste: c => c.segundos_periodo > 0 },
  { key: 'concluidos', label: 'Concluídos', teste: c => c.concluido },
  { key: 'todos', label: 'Todos', teste: () => true },
];

const ORDENACOES = [
  { key: 'tempo', label: 'Mais horas no período', cmp: (a, b) => b.segundos_periodo - a.segundos_periodo || b.segundos_total - a.segundos_total },
  { key: 'prazo', label: 'Prazo mais próximo', cmp: (a, b) => (a.prazo || '9999').localeCompare(b.prazo || '9999') },
  { key: 'progresso', label: 'Menos avançados', cmp: (a, b) => (a.progresso ?? -1) - (b.progresso ?? -1) },
];

const formatarHorario = (isoStr) => {
  const d = new Date(isoStr);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
};

function StatTile({ icon, label, value, sub, tom = 'text-slate-100' }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col gap-1">
      <div className="flex items-center gap-2 text-slate-400 text-xs font-bold uppercase tracking-widest">{icon} {label}</div>
      <div className={`text-3xl font-black ${tom}`}>{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

function Bloco({ titulo, icone, acoes, children }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 min-w-0">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">{icone} {titulo}</h3>
        {acoes}
      </div>
      {children}
    </div>
  );
}

function Barra({ pct, cor = '#10b981' }) {
  return (
    <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
      <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: cor }}/>
    </div>
  );
}

function Progresso({ valor }) {
  if (valor == null) return <span className="text-[10px] text-slate-600">sem etapas</span>;
  return (
    <div className="flex items-center gap-2 w-28">
      <Barra pct={valor} cor={valor === 100 ? '#10b981' : '#14b8a6'}/>
      <span className="text-[10px] font-bold text-slate-400 w-8 text-right">{valor}%</span>
    </div>
  );
}

function SeletorPeriodo({ periodo, setPeriodo, inicio, fim, setInicio, setFim }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <div className="flex items-center bg-slate-900 rounded-xl border border-slate-800 p-0.5">
        {PERIODOS.map(p => (
          <button key={p.key} onClick={() => setPeriodo(p.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${periodo === p.key ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow' : 'text-slate-300 hover:bg-white/10'}`}>
            {p.label}
          </button>
        ))}
      </div>
      {periodo === 'personalizado' && (
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <input type="date" value={inicio} max={fim} onChange={e => e.target.value && setInicio(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-100 outline-none focus:border-emerald-400 [color-scheme:dark]"/>
          até
          <input type="date" value={fim} min={inicio} onChange={e => e.target.value && setFim(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-100 outline-none focus:border-emerald-400 [color-scheme:dark]"/>
        </div>
      )}
    </div>
  );
}

function LinhaCard({ c, onAbrirCard, segundos }) {
  return (
    <button onClick={() => onAbrirCard(c.id)}
      className="w-full grid grid-cols-[1fr_auto] md:grid-cols-[minmax(0,1fr)_auto_auto_auto] items-center gap-x-4 gap-y-1.5 p-2.5 bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 rounded-lg text-left transition-colors">
      <div className="min-w-0 space-y-1">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: c.coluna_cor || '#64748b' }} title={c.coluna}/>
          <span className="text-sm font-bold text-slate-200 truncate">{c.titulo}</span>
          {c.prioridade !== 'Normal' && <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded shrink-0 ${PRIORIDADES_BADGE[c.prioridade]}`}>{c.prioridade}</span>}
        </div>
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-[10px] text-slate-500 mr-1">{c.coluna}</span>
          {c.responsaveis.map(nome => <span key={nome} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${userColor(nome)}`}>{nome}</span>)}
        </div>
      </div>
      <Progresso valor={c.progresso}/>
      <div className="text-right">
        <div className="text-xs font-mono font-bold text-slate-200">{formatarDuracao(segundos)}</div>
        {c.segundos_total != null && c.segundos_total !== segundos && <div className="text-[10px] text-slate-500 font-mono">{formatarDuracao(c.segundos_total)} no total</div>}
      </div>
      <div className={`text-[11px] font-bold text-right w-20 ${c.atrasado ? 'text-red-400' : c.concluido ? 'text-emerald-400' : 'text-slate-400'}`}>
        {c.concluido ? 'Concluído' : c.prazo ? formatarData(c.prazo) : 'sem prazo'}
        {c.atrasado && <div className="text-[9px] uppercase tracking-wider">atrasado</div>}
      </div>
    </button>
  );
}

function TrabalhandoAgora({ lista, recebido, onAbrirCard, onVerFuncionario }) {
  const agora = useAgora(lista.length > 0);
  if (lista.length === 0) return <p className="text-xs text-slate-500">Ninguém com cronômetro ligado agora.</p>;
  return (
    <div className="space-y-1.5">
      {lista.map(r => (
        <div key={r.user_id} className="flex items-center gap-3 p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"/>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"/>
          </span>
          <button onClick={() => onVerFuncionario(r.user_id)} className={`text-[11px] font-bold px-2 py-0.5 rounded-full shrink-0 hover:ring-1 hover:ring-white/40 ${userColor(r.usuario)}`}>{r.usuario}</button>
          <button onClick={() => r.card_id && onAbrirCard(r.card_id)} className="flex-1 min-w-0 text-left">
            <div className="text-sm text-slate-200 font-bold truncate hover:text-emerald-300">{!r.card_id && <span className="mr-1.5 px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300 text-[9px] font-black uppercase">atividade</span>}{r.card_titulo}</div>
            {r.etapa_texto && <div className="text-[11px] text-slate-500 truncate">em {r.etapa_texto}</div>}
          </button>
          <span className="font-mono text-sm font-bold text-emerald-300 tabular-nums shrink-0">
            {formatarRelogio(r.decorrido_segundos + segundosDesde(recebido, agora))}
          </span>
        </div>
      ))}
    </div>
  );
}

function VisaoEquipe({ dados, onAbrirCard, onVerFuncionario }) {
  const [filtro, setFiltro] = useState('abertos');
  const [ordem, setOrdem] = useState('tempo');

  const maxHoras = Math.max(1, ...dados.funcionarios.map(f => f.segundos));
  const filtroAtual = FILTROS_CARDS.find(f => f.key === filtro);
  const cards = dados.cards.filter(filtroAtual.teste).sort(ORDENACOES.find(o => o.key === ordem).cmp);
  const abertos = dados.cards.filter(c => !c.concluido).length;
  const atrasados = dados.cards.filter(c => c.atrasado).length;

  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile icon={<Clock size={14}/>} label="Horas no período" value={formatarDuracao(dados.total_segundos)}
          sub={`${dados.funcionarios.filter(f => f.segundos > 0).length} pessoa(s) registraram tempo`}/>
        <StatTile icon={<Timer size={14}/>} label="Trabalhando agora" value={dados.trabalhando_agora.length} tom="text-emerald-300"/>
        <StatTile icon={<Briefcase size={14}/>} label="Cards em aberto" value={abertos}/>
        <StatTile icon={<AlertTriangle size={14}/>} label="Atrasados" value={atrasados} tom={atrasados ? 'text-red-400' : 'text-slate-100'}/>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Bloco titulo="Trabalhando agora" icone={<Timer size={14} className="text-emerald-400"/>}>
          <TrabalhandoAgora lista={dados.trabalhando_agora} recebido={dados} onAbrirCard={onAbrirCard} onVerFuncionario={onVerFuncionario}/>
        </Bloco>

        <Bloco titulo="Horas por funcionário" icone={<Users size={14} className="text-indigo-400"/>}
          acoes={<span className="text-[10px] text-slate-500">clique para ver a ficha</span>}>
          <div className="space-y-1">
            {dados.funcionarios.map(f => (
              <button key={f.user_id} onClick={() => onVerFuncionario(f.user_id)} title={`Ver a ficha de ${f.nome}`}
                className="w-full flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-slate-800 transition-colors text-left group">
                <span className="w-32 shrink-0 flex items-center gap-1.5 min-w-0">
                  {f.rodando && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" title="Cronômetro ligado agora"/>}
                  <span className="text-xs font-bold text-slate-300 truncate">{f.nome}</span>
                </span>
                <Barra pct={f.segundos ? Math.max(4, (f.segundos / maxHoras) * 100) : 0} cor="#6366f1"/>
                <span className={`w-20 shrink-0 text-right text-xs font-mono font-bold ${f.segundos ? 'text-slate-200' : 'text-slate-600'}`}>{formatarDuracao(f.segundos)}</span>
                <span className="w-14 shrink-0 text-right text-[10px] text-slate-500">{f.cards} card{f.cards !== 1 ? 's' : ''}</span>
                <ChevronRight size={14} className="shrink-0 text-slate-600 group-hover:text-indigo-300 transition-colors"/>
              </button>
            ))}
          </div>
        </Bloco>
      </div>

      <Bloco titulo="Andamento dos cards" icone={<Briefcase size={14} className="text-teal-400"/>}
        acoes={
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center bg-slate-800 rounded-lg p-0.5">
              {FILTROS_CARDS.map(f => (
                <button key={f.key} onClick={() => setFiltro(f.key)}
                  className={`px-2 py-1 rounded-md text-[11px] font-bold transition-colors ${filtro === f.key ? 'bg-slate-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
                  {f.label}
                </button>
              ))}
            </div>
            <select value={ordem} onChange={e => setOrdem(e.target.value)}
              className="text-[11px] font-bold bg-slate-800 text-slate-300 border border-slate-700 rounded-lg px-2 py-1 outline-none">
              {ORDENACOES.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
            </select>
          </div>
        }>
        {cards.length === 0 ? (
          <p className="text-xs text-slate-500">Nenhum card neste filtro.</p>
        ) : (
          <div className="space-y-1.5">
            {cards.map(c => <LinhaCard key={c.id} c={c} onAbrirCard={onAbrirCard} segundos={c.segundos_periodo}/>)}
          </div>
        )}
      </Bloco>
    </>
  );
}

function FichaFuncionario({ ficha, onVoltar, onAbrirCard }) {
  const [verTodos, setVerTodos] = useState(false);
  const maxDia = Math.max(1, ...ficha.por_dia.map(d => d.segundos));
  // Atividades fora de card (saída de campo...) entram na mesma lista, em roxo.
  const porItem = [
    ...ficha.por_card.map(c => ({ ...c, chave: c.card_id })),
    ...(ficha.por_atividade || []).map(a => ({ ...a, chave: a.atividade_id, atividade: true })),
  ];
  const maxCard = Math.max(1, ...porItem.map(c => c.segundos));
  const diasComTempo = ficha.por_dia.filter(d => d.segundos > 0).length;
  const atrasados = ficha.cards_responsavel.filter(c => c.atrasado).length;
  const registros = verTodos ? ficha.registros : ficha.registros.slice(0, 10);
  const muitosDias = ficha.por_dia.length > 31;

  return (
    <>
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={onVoltar} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-slate-300 bg-slate-900 border border-slate-800 hover:bg-slate-800 transition-colors">
          <ArrowLeft size={14}/> Equipe
        </button>
        <span className={`text-sm font-black px-3 py-1 rounded-full ${userColor(ficha.usuario.nome)}`}>{ficha.usuario.nome}</span>
        {ficha.rodando ? (
          <button onClick={() => ficha.rodando.card_id && onAbrirCard(ficha.rodando.card_id)} className="text-xs text-emerald-300 hover:underline truncate">
            ● trabalhando agora em "{ficha.rodando.card_titulo}"{ficha.rodando.etapa_texto ? ` — ${ficha.rodando.etapa_texto}` : ''}
          </button>
        ) : <span className="text-xs text-slate-500">sem cronômetro ligado</span>}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile icon={<Clock size={14}/>} label="Horas no período" value={formatarDuracao(ficha.total_segundos)}
          sub={diasComTempo ? `média de ${formatarDuracao(ficha.total_segundos / diasComTempo)} por dia trabalhado` : 'nenhum registro no período'}/>
        <StatTile icon={<Briefcase size={14}/>} label="Cards trabalhados" value={ficha.por_card.length} sub="no período"/>
        <StatTile icon={<CheckCircle2 size={14}/>} label="Etapas concluídas" value={ficha.etapas_concluidas} sub="desde sempre"/>
        <StatTile icon={<AlertTriangle size={14}/>} label="Atrasados" value={atrasados} tom={atrasados ? 'text-red-400' : 'text-slate-100'}
          sub={`de ${ficha.cards_responsavel.filter(c => !c.concluido).length} card(s) em aberto sob responsabilidade`}/>
      </div>

      <Bloco titulo="Horas por dia" icone={<Clock size={14} className="text-indigo-400"/>}>
        <div className="overflow-x-auto custom-scrollbar">
          <div className="flex items-end gap-1 h-40 pt-4" style={{ minWidth: muitosDias ? ficha.por_dia.length * 14 : undefined }}>
            {ficha.por_dia.map(d => {
              const [, m, dia] = d.data.split('-');
              return (
                <div key={d.data} className="flex-1 min-w-[10px] h-full flex flex-col items-center justify-end gap-1 group" title={`${dia}/${m}: ${formatarDuracao(d.segundos)}`}>
                  <span className="text-[9px] font-mono text-slate-400 opacity-0 group-hover:opacity-100 whitespace-nowrap">{d.segundos ? formatarDuracao(d.segundos) : ''}</span>
                  <div className="w-full max-w-[36px] rounded-t bg-indigo-500/80 group-hover:bg-indigo-400 transition-colors"
                    style={{ height: d.segundos ? `${Math.max(3, (d.segundos / maxDia) * 100)}%` : 0 }}/>
                  {!muitosDias && <span className="text-[9px] text-slate-500 font-mono">{dia}/{m}</span>}
                </div>
              );
            })}
          </div>
        </div>
      </Bloco>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Bloco titulo="Horas por card e atividade" icone={<Briefcase size={14} className="text-teal-400"/>}>
          {porItem.length === 0 ? <p className="text-xs text-slate-500">Nenhuma hora registrada no período.</p> : (
            <div className="space-y-1">
              {porItem.map(c => (
                <button key={c.chave} onClick={() => !c.atividade && onAbrirCard(c.card_id)}
                  className={`w-full flex items-center gap-3 px-2 py-1.5 rounded-lg transition-colors text-left ${c.atividade ? 'cursor-default' : 'hover:bg-slate-800'}`}
                  title={c.atividade ? 'Atividade fora de card' : undefined}>
                  <span className={`w-40 shrink-0 text-xs font-bold truncate ${c.atividade ? 'text-violet-300' : 'text-slate-300'}`}>{c.titulo}</span>
                  <Barra pct={Math.max(4, (c.segundos / maxCard) * 100)} cor={c.atividade ? '#8b5cf6' : '#14b8a6'}/>
                  <span className="w-20 shrink-0 text-right text-xs font-mono font-bold text-slate-200">{formatarDuracao(c.segundos)}</span>
                </button>
              ))}
            </div>
          )}
        </Bloco>

        <Bloco titulo="Registros do período" icone={<Timer size={14} className="text-emerald-400"/>}>
          {ficha.registros.length === 0 ? <p className="text-xs text-slate-500">Nenhum registro.</p> : (
            <div className="space-y-0.5">
              {registros.map(r => (
                <div key={r.id} className="flex items-center gap-2 text-xs py-1">
                  <span className="text-slate-500 font-mono shrink-0">{formatarHorario(r.inicio)}</span>
                  <button onClick={() => r.card_id && onAbrirCard(r.card_id)} className="flex-1 min-w-0 text-left truncate text-slate-300 hover:text-emerald-300">
                    {!r.card_id && <span className="mr-1.5 px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300 text-[9px] font-black uppercase">atividade</span>}{r.card_titulo}{r.etapa_texto && <span className="text-slate-500"> · {r.etapa_texto}</span>}
                  </button>
                  <span className="font-mono text-slate-300 shrink-0">{r.fim ? formatarDuracao(r.segundos) : <span className="text-emerald-300">em andamento</span>}</span>
                </div>
              ))}
              {ficha.registros.length > 10 && (
                <button onClick={() => setVerTodos(v => !v)} className="text-[11px] font-bold text-emerald-400 hover:text-emerald-300 pt-1">
                  {verTodos ? 'Mostrar menos' : `Ver todos (${ficha.registros.length})`}
                </button>
              )}
            </div>
          )}
        </Bloco>
      </div>

      <Bloco titulo="Cards sob responsabilidade" icone={<Users size={14} className="text-indigo-400"/>}>
        {ficha.cards_responsavel.length === 0 ? <p className="text-xs text-slate-500">Não é responsável por nenhum card.</p> : (
          <div className="space-y-1.5">
            {ficha.cards_responsavel.map(c => {
              const seg = ficha.por_card.find(p => p.card_id === c.id)?.segundos || 0;
              return <LinhaCard key={c.id} c={c} onAbrirCard={onAbrirCard} segundos={seg}/>;
            })}
          </div>
        )}
      </Bloco>
    </>
  );
}

function SeletorPessoa({ usuarios, rodando, selecionado, onSelecionar }) {
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState('');
  const atual = usuarios.find(u => u.id === selecionado);
  const termo = busca.trim().toLowerCase();
  const filtrados = usuarios.filter(u => !termo || u.nome.toLowerCase().includes(termo));
  const escolher = (id) => { onSelecionar(id); setAberto(false); setBusca(''); };

  return (
    <div className="relative">
      <button onClick={() => setAberto(a => !a)}
        className={`flex items-center gap-2 pl-2.5 pr-2 py-1.5 rounded-xl border text-xs font-bold transition-colors min-w-[180px] ${atual ? 'bg-indigo-500/10 border-indigo-500/40 text-slate-100' : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800'}`}>
        {atual ? <User size={14} className="text-indigo-300 shrink-0"/> : <Users size={14} className="text-slate-400 shrink-0"/>}
        <span className="flex-1 text-left truncate">{atual ? atual.nome : 'Toda a equipe'}</span>
        <ChevronDown size={14} className="text-slate-500 shrink-0"/>
      </button>
      {aberto && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAberto(false)}/>
          <div className="absolute top-full mt-1 left-0 sm:left-auto sm:right-0 w-64 bg-slate-800 rounded-xl shadow-2xl border border-slate-700 z-50 overflow-hidden">
            <div className="p-2 border-b border-slate-700 flex items-center gap-2">
              <Search size={13} className="text-slate-500 shrink-0"/>
              <input autoFocus value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar pessoa..."
                onKeyDown={e => { if (e.key === 'Escape') setAberto(false); if (e.key === 'Enter' && filtrados.length === 1) escolher(filtrados[0].id); }}
                className="flex-1 min-w-0 bg-transparent text-xs text-slate-100 outline-none placeholder:text-slate-500"/>
            </div>
            <div className="max-h-72 overflow-y-auto custom-scrollbar py-1">
              {!termo && (
                <button onClick={() => escolher(null)} className="w-full flex items-center gap-2 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-700 transition-colors">
                  <Users size={13} className="text-slate-400"/> <span className="flex-1 text-left">Toda a equipe</span>
                  {!selecionado && <Check size={13} className="text-emerald-400"/>}
                </button>
              )}
              {filtrados.map(u => (
                <button key={u.id} onClick={() => escolher(u.id)} className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-slate-700 transition-colors">
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full truncate ${userColor(u.nome)}`}>{u.nome}</span>
                  {rodando.has(u.id) && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" title="Cronômetro ligado agora"/>}
                  <span className="flex-1"/>
                  {selecionado === u.id && <Check size={13} className="text-emerald-400 shrink-0"/>}
                </button>
              ))}
              {filtrados.length === 0 && <p className="px-3 py-2 text-xs text-slate-500">Ninguém encontrado.</p>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function GestaoView({ onAbrirCard, allUsers }) {
  const [periodo, setPeriodo] = useState('semana');
  const [inicioPers, setInicioPers] = useState(() => iso(new Date()));
  const [fimPers, setFimPers] = useState(() => iso(new Date()));
  const [funcionarioId, setFuncionarioId] = useState(null);
  const [dados, setDados] = useState(null);
  const [ficha, setFicha] = useState(null);
  const [erro, setErro] = useState('');
  const [recarga, setRecarga] = useState(0);

  const [inicio, fim] = periodo === 'personalizado'
    ? [inicioPers, fimPers]
    : PERIODOS.find(p => p.key === periodo).calc(new Date()).map(iso);

  useEffect(() => {
    let cancelado = false;
    const url = funcionarioId
      ? `${API}/gestao/funcionario/${funcionarioId}?inicio=${inicio}&fim=${fim}`
      : `${API}/gestao/visao-geral?inicio=${inicio}&fim=${fim}`;
    authFetch(url).then(async r => {
      const corpo = await r.json().catch(() => null);
      if (cancelado) return;
      if (!r.ok) { setErro(corpo?.detail || 'Não foi possível carregar a gestão.'); return; }
      setErro('');
      const recebido = { ...corpo, recebidoEm: Date.now() };
      if (funcionarioId) setFicha(recebido); else setDados(recebido);
    }).catch(() => !cancelado && setErro('Falha de conexão com o servidor.'));
    return () => { cancelado = true; };
  }, [inicio, fim, funcionarioId, recarga]);

  // Gestão é pra ficar aberta numa tela: atualiza sozinha a cada minuto.
  useEffect(() => {
    const t = setInterval(() => setRecarga(n => n + 1), 60000);
    return () => clearInterval(t);
  }, []);

  const verFuncionario = (id) => { if (id !== funcionarioId) { setFicha(null); setFuncionarioId(id); } };
  const usuarios = [...(allUsers || [])].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  const rodandoIds = new Set((dados?.trabalhando_agora || []).map(r => r.user_id));
  const carregando = funcionarioId ? !ficha : !dados;

  return (
    <div className="absolute inset-0 overflow-y-auto custom-scrollbar px-4 md:px-8 py-6 space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="text-lg font-black text-slate-100 flex items-center gap-2"><Users size={18} className="text-emerald-400"/> Gestão</h2>
        <div className="flex items-center gap-2 flex-wrap">
          <SeletorPessoa usuarios={usuarios} rodando={rodandoIds} selecionado={funcionarioId} onSelecionar={verFuncionario}/>
          <SeletorPeriodo periodo={periodo} setPeriodo={setPeriodo} inicio={inicioPers} fim={fimPers}
            setInicio={setInicioPers} setFim={setFimPers}/>
          <button onClick={() => setRecarga(n => n + 1)} title="Atualizar" className="p-2 rounded-lg text-slate-400 hover:text-white bg-slate-900 border border-slate-800 hover:bg-slate-800 transition-colors">
            <RefreshCw size={14}/>
          </button>
        </div>
      </div>

      {erro && <div className="text-sm text-red-400">{erro}</div>}
      {carregando && !erro && <div className="text-white/40 text-sm font-bold">Carregando...</div>}

      {!carregando && (funcionarioId
        ? <FichaFuncionario ficha={ficha} onVoltar={() => setFuncionarioId(null)} onAbrirCard={onAbrirCard}/>
        : <VisaoEquipe dados={dados} onAbrirCard={onAbrirCard} onVerFuncionario={verFuncionario}/>)}
    </div>
  );
}
