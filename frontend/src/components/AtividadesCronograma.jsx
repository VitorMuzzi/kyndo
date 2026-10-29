import React, { useState } from 'react';
import { CalendarClock, Play, Plus, Square, Trash2, X, History } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { formatarDuracao } from '../cronometro.js';

const SUGESTOES = ['Saída de campo', 'Reunião', 'Visita técnica', 'Treinamento', 'Deslocamento'];
const CAMPO = 'w-full p-2 bg-slate-950 text-slate-100 border border-slate-700 rounded-lg outline-none focus:border-violet-500 text-sm';

// "AAAA-MM-DDTHH:MM" no fuso de quem olha — o formato do <input type="datetime-local">.
const paraCampo = (d) => {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};
const dataHoraBR = (iso) => (iso ? new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');

const comRecebido = (cronometro) => (cronometro ? { ...cronometro, recebidoEm: Date.now() } : null);

async function chamar(url, metodo, corpo) {
  const res = await authFetch(url, { method: metodo, body: corpo ? JSON.stringify(corpo) : undefined }).catch(() => null);
  const data = await res?.json().catch(() => ({}));
  if (!res?.ok) throw new Error(data?.detail || 'Não foi possível salvar.');
  return data;
}

function Janela({ titulo, onFechar, children }) {
  return (
    <div className="fixed inset-0 z-[230] bg-black/60 backdrop-blur-sm flex items-center justify-center p-3" onClick={onFechar}>
      <div className="w-full max-w-lg max-h-[90dvh] flex flex-col bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
          <h2 className="text-base font-black text-white">{titulo}</h2>
          <button onClick={onFechar} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10" title="Fechar"><X size={18}/></button>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-5 space-y-4">{children}</div>
      </div>
    </div>
  );
}

function Intervalo({ inicio, fim, onInicio, onFim }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div>
        <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Início</label>
        <input type="datetime-local" value={inicio} onChange={e => onInicio(e.target.value)} className={CAMPO}/>
      </div>
      <div>
        <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Fim</label>
        <input type="datetime-local" value={fim} onChange={e => onFim(e.target.value)} className={CAMPO}/>
      </div>
    </div>
  );
}

const MODOS = [
  { val: 'agora', label: 'Começar agora', dica: 'Liga o cronômetro nesta atividade (desliga o que estiver ligado).' },
  { val: 'lancar', label: 'Lançar tempo já feito', dica: 'Para registrar depois uma atividade que já aconteceu.' },
  { val: 'agendar', label: 'Agendar', dica: 'Marca no cronograma para depois. Na hora, é só começar o cronômetro ou lançar o tempo.' },
];

export function NovaAtividadeModal({ onFechar, onCriada, onCronometroChange }) {
  const agora = new Date();
  const amanha8 = new Date(agora); amanha8.setDate(agora.getDate() + 1); amanha8.setHours(8, 0, 0, 0);
  const amanha17 = new Date(amanha8); amanha17.setHours(17);
  const [titulo, setTitulo] = useState('');
  const [modo, setModo] = useState('agora');
  const [lancar, setLancar] = useState({ inicio: paraCampo(new Date(agora.getTime() - 3600000)), fim: paraCampo(agora) });
  const [agendar, setAgendar] = useState({ inicio: paraCampo(amanha8), fim: paraCampo(amanha17) });
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);

  const intervalo = modo === 'lancar' ? lancar : agendar;
  const setIntervalo = modo === 'lancar' ? setLancar : setAgendar;

  const salvar = async (e) => {
    e.preventDefault();
    setErro('');
    setSalvando(true);
    try {
      const r = await chamar(`${API}/atividades`, 'POST', { titulo, modo, ...(modo === 'agora' ? {} : intervalo) });
      if (modo === 'agora') onCronometroChange(comRecebido(r.cronometro));
      onCriada();
    } catch (err) {
      setErro(err.message);
      setSalvando(false);
    }
  };

  return (
    <Janela titulo="Nova atividade" onFechar={onFechar}>
      <form onSubmit={salvar} className="space-y-4">
        <div>
          <label className="block text-xs font-bold text-slate-400 uppercase mb-1">O que é</label>
          <input autoFocus value={titulo} onChange={e => setTitulo(e.target.value)} maxLength={80} placeholder="Ex.: Saída de campo — cliente X" className={CAMPO}/>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {SUGESTOES.map(s => (
              <button key={s} type="button" onClick={() => setTitulo(s)}
                className="px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-[11px] text-slate-300 hover:border-violet-500">{s}</button>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex flex-wrap rounded-lg overflow-hidden border border-slate-700 w-fit">
            {MODOS.map(m => (
              <button key={m.val} type="button" onClick={() => setModo(m.val)}
                className={`px-3 py-1.5 text-xs font-bold transition-colors ${modo === m.val ? 'bg-violet-600 text-white' : 'bg-slate-950 text-slate-400 hover:text-slate-200'}`}>
                {m.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500">{MODOS.find(m => m.val === modo).dica}</p>
        </div>
        {modo !== 'agora' && (
          <Intervalo inicio={intervalo.inicio} fim={intervalo.fim}
            onInicio={v => setIntervalo(i => ({ ...i, inicio: v }))} onFim={v => setIntervalo(i => ({ ...i, fim: v }))}/>
        )}
        {erro && <p className="text-xs font-bold text-red-400">{erro}</p>}
        <button type="submit" disabled={salvando}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-bold disabled:opacity-60">
          {modo === 'agora' ? <Play size={14}/> : modo === 'lancar' ? <Plus size={14}/> : <CalendarClock size={14}/>}
          {modo === 'agora' ? 'Começar cronômetro' : modo === 'lancar' ? 'Lançar tempo' : 'Agendar'}
        </button>
      </form>
    </Janela>
  );
}

export function AtividadeDetalheModal({ atividade, onFechar, onMudou, onCronometroChange }) {
  const [atv, setAtv] = useState(atividade);
  const [titulo, setTitulo] = useState(atividade.titulo);
  const [agenda, setAgenda] = useState({
    inicio: atividade.agendada_inicio ? paraCampo(new Date(atividade.agendada_inicio)) : '',
    fim: atividade.agendada_fim ? paraCampo(new Date(atividade.agendada_fim)) : '',
  });
  const agora = new Date();
  const [periodo, setPeriodo] = useState(() => ({
    inicio: atividade.agendada_inicio && new Date(atividade.agendada_inicio) < agora ? paraCampo(new Date(atividade.agendada_inicio)) : paraCampo(new Date(agora.getTime() - 3600000)),
    fim: atividade.agendada_fim && new Date(atividade.agendada_fim) < agora ? paraCampo(new Date(atividade.agendada_fim)) : paraCampo(agora),
  }));
  const [lancando, setLancando] = useState(false);
  const [erro, setErro] = useState('');
  const minha = atv.minha;

  const executar = async (fn) => {
    setErro('');
    try { await fn(); onMudou(); } catch (err) { setErro(err.message); }
  };

  const salvarDados = () => executar(async () => {
    setAtv(await chamar(`${API}/atividades/${atv.id}`, 'PUT', {
      titulo, agendada_inicio: agenda.inicio || null, agendada_fim: agenda.fim || null,
    }));
  });
  const comecar = () => executar(async () => {
    const r = await chamar(`${API}/atividades/${atv.id}/iniciar`, 'POST');
    setAtv(r.atividade);
    onCronometroChange(comRecebido(r.cronometro));
  });
  const parar = () => executar(async () => {
    await chamar(`${API}/tempo/parar`, 'POST');
    onCronometroChange(null);
    onFechar();
  });
  const lancar = () => executar(async () => {
    setAtv(await chamar(`${API}/atividades/${atv.id}/registros`, 'POST', periodo));
    setLancando(false);
  });
  const apagarPeriodo = (id) => executar(async () => {
    if (!confirm('Apagar este período?')) throw new Error('');
    await chamar(`${API}/tempo/${id}`, 'DELETE');
    setAtv(a => ({ ...a, registros: a.registros.filter(r => r.id !== id), total_segundos: a.total_segundos - (a.registros.find(r => r.id === id)?.segundos || 0) }));
  });
  const apagar = () => executar(async () => {
    if (!confirm(`Excluir a atividade "${atv.titulo}" e todo o tempo registrado nela?`)) throw new Error('');
    await chamar(`${API}/atividades/${atv.id}`, 'DELETE');
    if (atv.em_andamento) onCronometroChange(null);
    onFechar();
  });

  const mudouDados = titulo !== atv.titulo
    || (agenda.inicio || null) !== (atv.agendada_inicio ? paraCampo(new Date(atv.agendada_inicio)) : null)
    || (agenda.fim || null) !== (atv.agendada_fim ? paraCampo(new Date(atv.agendada_fim)) : null);

  return (
    <Janela titulo={minha ? 'Atividade' : `Atividade de ${atv.usuario}`} onFechar={onFechar}>
      <div>
        <label className="block text-xs font-bold text-slate-400 uppercase mb-1">O que é</label>
        {minha ? <input value={titulo} onChange={e => setTitulo(e.target.value)} maxLength={80} className={CAMPO}/>
          : <p className="text-sm font-bold text-slate-100">{atv.titulo}</p>}
      </div>

      <div className="space-y-2">
        <div className="text-xs font-bold text-slate-400 uppercase">Agendada para</div>
        {minha ? (
          <>
            <Intervalo inicio={agenda.inicio} fim={agenda.fim}
              onInicio={v => setAgenda(a => ({ ...a, inicio: v }))} onFim={v => setAgenda(a => ({ ...a, fim: v }))}/>
            {(agenda.inicio || agenda.fim) && (
              <button onClick={() => setAgenda({ inicio: '', fim: '' })} className="text-[11px] font-bold text-slate-400 hover:text-slate-200">Tirar o agendamento</button>
            )}
          </>
        ) : (
          <p className="text-sm text-slate-300">{atv.agendada_inicio ? `${dataHoraBR(atv.agendada_inicio)} até ${dataHoraBR(atv.agendada_fim)}` : 'Sem agendamento'}</p>
        )}
        {minha && mudouDados && (
          <button onClick={salvarDados} className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold">Salvar alterações</button>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-xs font-bold text-slate-400 uppercase"><History size={13}/> Tempo registrado</span>
          <span className="text-sm font-black text-violet-300">{formatarDuracao(atv.total_segundos)}</span>
        </div>
        {atv.registros.length === 0 ? <p className="text-xs text-slate-500">Nenhum tempo registrado ainda.</p> : (
          <ul className="space-y-1">
            {atv.registros.map(r => (
              <li key={r.id} className="flex items-center gap-2 text-xs text-slate-300 bg-slate-800/60 rounded-lg px-2.5 py-1.5">
                <span className="flex-1">{dataHoraBR(r.inicio)} → {r.fim ? dataHoraBR(r.fim) : <span className="text-emerald-300 font-bold">agora</span>}</span>
                <span className="font-mono font-bold">{formatarDuracao(r.segundos)}</span>
                {minha && (
                  <button onClick={() => apagarPeriodo(r.id)} className="p-1 rounded text-slate-500 hover:text-red-300 hover:bg-red-500/10" title="Apagar este período"><Trash2 size={12}/></button>
                )}
              </li>
            ))}
          </ul>
        )}
        {minha && lancando && (
          <div className="space-y-2 p-3 rounded-xl border border-slate-700">
            <Intervalo inicio={periodo.inicio} fim={periodo.fim}
              onInicio={v => setPeriodo(p => ({ ...p, inicio: v }))} onFim={v => setPeriodo(p => ({ ...p, fim: v }))}/>
            <div className="flex gap-3">
              <button onClick={lancar} className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold">Lançar</button>
              <button onClick={() => setLancando(false)} className="text-xs font-bold text-slate-400 hover:text-slate-200">Cancelar</button>
            </div>
          </div>
        )}
      </div>

      {erro && <p className="text-xs font-bold text-red-400">{erro}</p>}

      {minha && (
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800">
          {atv.em_andamento ? (
            <button onClick={parar} className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-red-500/15 text-red-300 hover:bg-red-500/30 text-xs font-bold">
              <Square size={12} fill="currentColor"/> Parar cronômetro
            </button>
          ) : (
            <button onClick={comecar} className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold">
              <Play size={12}/> Começar cronômetro
            </button>
          )}
          {!lancando && (
            <button onClick={() => setLancando(true)} className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold">
              <Plus size={12}/> Lançar tempo já feito
            </button>
          )}
          <div className="flex-1"/>
          <button onClick={apagar} className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-red-300 hover:bg-red-500/10 text-xs font-bold">
            <Trash2 size={12}/> Excluir
          </button>
        </div>
      )}
    </Janela>
  );
}
