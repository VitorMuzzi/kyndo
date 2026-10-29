import React, { useState } from 'react';
import { Plus, Trash2, X } from 'lucide-react';
import { API, authFetch } from '../api.js';

// Campos que o modelo pode usar; a tela de Relatórios troca pelos dados do dia.
const CAMPOS_MODELO = [
  { campo: '{data}', dica: 'data do relatório (29/10/2026)' },
  { campo: '{dia_da_semana}', dica: 'quarta-feira, quinta-feira…' },
  { campo: '{nome}', dica: 'o seu nome' },
  { campo: '{tempo_total}', dica: 'tempo cronometrado no dia' },
  { campo: '{resumo}', dica: 'os cards do dia, com tempo e etapas concluídas' },
];

const CAMPO = 'w-full p-2 bg-slate-950 text-slate-100 border border-slate-700 rounded-lg outline-none focus:border-emerald-500 text-sm';

// Janela para criar, editar e apagar os modelos de relatório. `inicial`
// abre já com um modelo novo preenchido (o "Salvar texto atual como modelo").
export default function ModelosRelatorioModal({ modelos, onMudou, onFechar, inicial }) {
  const [sel, setSel] = useState(() => (inicial ? { id: null, nome: '', conteudo: inicial } : modelos[0] || { id: null, nome: '', conteudo: '' }));
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);

  const abrir = (m) => { setSel(m); setErro(''); };

  const salvar = async () => {
    setErro('');
    setSalvando(true);
    const url = sel.id ? `${API}/relatorios/modelos/${sel.id}` : `${API}/relatorios/modelos`;
    const res = await authFetch(url, { method: sel.id ? 'PUT' : 'POST', body: JSON.stringify({ nome: sel.nome, conteudo: sel.conteudo }) }).catch(() => null);
    const data = await res?.json().catch(() => ({}));
    setSalvando(false);
    if (!res?.ok) { setErro(data?.detail || 'Não foi possível salvar.'); return; }
    setSel(data);
    onMudou();
  };

  const apagar = async () => {
    if (!sel.id || !confirm(`Apagar o modelo "${sel.nome}"?`)) return;
    const res = await authFetch(`${API}/relatorios/modelos/${sel.id}`, { method: 'DELETE' });
    if (!res.ok) { setErro('Não foi possível apagar.'); return; }
    const resto = modelos.filter(m => m.id !== sel.id);
    setSel(resto[0] || { id: null, nome: '', conteudo: '' });
    onMudou();
  };

  const inserirCampo = (campo) => setSel(s => ({ ...s, conteudo: `${s.conteudo}${s.conteudo && !/\s$/.test(s.conteudo) ? ' ' : ''}${campo}` }));

  return (
    <div className="fixed inset-0 z-[230] bg-black/60 backdrop-blur-sm flex items-center justify-center p-3" onClick={onFechar}>
      <div className="w-full max-w-4xl max-h-[90dvh] flex flex-col bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
          <h2 className="text-base font-black text-white">Modelos de relatório</h2>
          <button onClick={onFechar} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10" title="Fechar"><X size={18}/></button>
        </div>

        <div className="flex-1 min-h-0 flex flex-col md:flex-row">
          {/* Lista */}
          <div className="md:w-56 shrink-0 border-b md:border-b-0 md:border-r border-slate-800 p-3 space-y-1 overflow-y-auto custom-scrollbar max-h-40 md:max-h-none">
            <button onClick={() => abrir({ id: null, nome: '', conteudo: '' })}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-bold transition-colors ${!sel.id ? 'bg-emerald-500/10 text-emerald-300' : 'text-slate-300 hover:bg-white/5'}`}>
              <Plus size={14}/> Novo modelo
            </button>
            {modelos.map(m => (
              <button key={m.id} onClick={() => abrir(m)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors ${sel.id === m.id ? 'bg-emerald-500/10 text-emerald-300 font-bold' : 'text-slate-300 hover:bg-white/5'}`}>
                {m.nome}
              </button>
            ))}
          </div>

          {/* Editor */}
          <div className="flex-1 min-w-0 p-4 md:p-5 space-y-3 overflow-y-auto custom-scrollbar">
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Nome</label>
              <input value={sel.nome} onChange={e => setSel(s => ({ ...s, nome: e.target.value }))} maxLength={60}
                placeholder="Ex.: Relatório diário" className={CAMPO}/>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Texto</label>
              <textarea value={sel.conteudo} onChange={e => setSel(s => ({ ...s, conteudo: e.target.value }))}
                placeholder={'Ex.:\nRelatório de {data}\n\nO que fiz:\n{resumo}\n\nPendências:\n- '}
                className={`${CAMPO} min-h-[220px] leading-relaxed resize-y`}/>
            </div>
            <div className="space-y-1">
              <div className="text-[11px] text-slate-500">Campos preenchidos sozinhos ao usar o modelo — clique para inserir:</div>
              <div className="flex flex-wrap gap-1.5">
                {CAMPOS_MODELO.map(c => (
                  <button key={c.campo} onClick={() => inserirCampo(c.campo)} title={c.dica}
                    className="px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-[11px] font-mono text-emerald-300 hover:border-emerald-500">
                    {c.campo}
                  </button>
                ))}
              </div>
            </div>
            {erro && <p className="text-xs font-bold text-red-400">{erro}</p>}
            <div className="flex items-center gap-3 pt-1">
              <button onClick={salvar} disabled={salvando}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold disabled:opacity-60">
                {salvando ? 'Salvando…' : sel.id ? 'Salvar alterações' : 'Criar modelo'}
              </button>
              {sel.id && (
                <button onClick={apagar} className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-bold text-red-300 hover:bg-red-500/10">
                  <Trash2 size={14}/> Apagar
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
