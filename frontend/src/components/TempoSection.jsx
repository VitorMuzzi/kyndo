import React, { useEffect, useState } from 'react';
import { Play, Square, Timer, Trash2 } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { userColor } from '../constants.jsx';
import { formatarDuracao, formatarRelogio, iniciarCronometro, pararCronometro, segundosDesde, useAgora, useDecorrido } from '../cronometro.js';

const REGISTROS_VISIVEIS = 5;

const formatarInicio = (iso) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
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

export default function TempoSection({ cardId, usuario, checklistSalvo, mostrarEtapas, cronometro, onCronometroChange }) {
  const [dados, setDados] = useState(null);
  const [etapaEscolhida, setEtapaEscolhida] = useState('');
  const [erro, setErro] = useState('');
  const [verTodos, setVerTodos] = useState(false);

  const rodandoAqui = cronometro?.card_id === cardId;
  const decorrido = useDecorrido(rodandoAqui ? cronometro : null);
  const agora = useAgora(rodandoAqui);
  const etapas = listarEtapas(checklistSalvo);
  const textoDaEtapa = (id) => etapas.find(e => e.id === id)?.texto || 'Etapa removida';

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
      onCronometroChange(await iniciarCronometro(cardId, etapaEscolhida));
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

  const apagarRegistro = async (id) => {
    if (!window.confirm('Apagar este registro de tempo?')) return;
    const res = await authFetch(`${API}/tempo/${id}`, { method: 'DELETE' });
    if (!res.ok) { setErro('Não foi possível apagar o registro.'); return; }
    if (cronometro?.id === id) onCronometroChange(null);
    else carregar();
  };

  // Os totais vêm do servidor na hora da busca; o cronômetro próprio rodando
  // aqui continua somando na tela até a próxima busca.
  const extra = rodandoAqui && dados ? segundosDesde(dados, agora) : 0;
  const registros = dados?.registros || [];
  const registrosVisiveis = verTodos ? registros : registros.slice(0, REGISTROS_VISIVEIS);
  // A linha de quem está com o cronômetro rodando aqui soma ao vivo, como o total.
  const porPessoa = (dados?.por_pessoa || [])
    .map(p => (p.usuario === usuario ? { ...p, segundos: p.segundos + extra } : p))
    .sort((a, b) => b.segundos - a.segundos);
  if (rodandoAqui && dados && !porPessoa.some(p => p.usuario === usuario)) porPessoa.push({ usuario, segundos: extra });
  const maxPessoa = Math.max(1, ...porPessoa.map(p => p.segundos));
  const etapasComTempo = mostrarEtapas
    ? Object.entries(dados?.por_etapa || {}).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 text-slate-300 font-bold text-sm"><Timer size={16}/> Tempo</div>
        {dados && (
          <div className="text-[11px] text-slate-400">
            Total <span className="font-bold text-slate-200">{formatarDuracao(dados.total_segundos + extra)}</span>
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
            {mostrarEtapas && cronometro.etapa_texto && <div className="text-[11px] text-slate-400 truncate">em {cronometro.etapa_texto}</div>}
          </div>
          <button onClick={parar} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/15 text-red-300 hover:bg-red-500/30 text-xs font-bold transition-colors">
            <Square size={12} fill="currentColor"/> Parar
          </button>
        </div>
      ) : (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            {mostrarEtapas && etapas.length > 0 && (
              <select value={etapaEscolhida} onChange={e => setEtapaEscolhida(e.target.value)}
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

      {etapasComTempo.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Por etapa</div>
          {etapasComTempo.map(([id, seg]) => (
            <div key={id} className="flex items-center justify-between gap-2 text-xs">
              <span className="text-slate-300 truncate">{textoDaEtapa(id)}</span>
              <span className="text-slate-400 font-mono shrink-0">{formatarDuracao(seg)}</span>
            </div>
          ))}
        </div>
      )}

      {registros.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
            {dados.pode_ver_equipe ? 'Registros' : 'Seus registros'}
          </div>
          {registrosVisiveis.map(r => (
            <div key={r.id} className="flex items-center gap-2 text-xs py-1 group">
              <span className="text-slate-500 font-mono shrink-0">{formatarInicio(r.inicio)}</span>
              {dados.pode_ver_equipe && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0 ${userColor(r.usuario)}`}>{r.usuario}</span>}
              <span className="text-slate-400 truncate flex-1">{mostrarEtapas && r.item_id ? textoDaEtapa(r.item_id) : ''}</span>
              <span className="font-mono text-slate-300 shrink-0">
                {r.fim ? formatarDuracao(r.segundos) : <span className="text-emerald-300">em andamento</span>}
              </span>
              {r.meu && (
                <button onClick={() => apagarRegistro(r.id)} className="shrink-0 text-slate-600 hover:text-red-400 md:opacity-0 md:group-hover:opacity-100 transition-opacity" title="Apagar registro">
                  <Trash2 size={12}/>
                </button>
              )}
            </div>
          ))}
          {registros.length > REGISTROS_VISIVEIS && (
            <button onClick={() => setVerTodos(v => !v)} className="text-[11px] font-bold text-emerald-400 hover:text-emerald-300">
              {verTodos ? 'Mostrar menos' : `Ver todos (${registros.length})`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
