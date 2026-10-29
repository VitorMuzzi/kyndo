import React, { useEffect, useState } from 'react';
import { Check, X } from 'lucide-react';
import { API, authFetch } from '../api.js';

const DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];  // 0 = segunda, como no servidor

// Configuração do envio automático do relatório do dia.
export default function EnvioAutomaticoModal({ gestores, onFechar, onSalvo }) {
  const [cfg, setCfg] = useState(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    authFetch(`${API}/relatorios/automatico`).then(r => (r.ok ? r.json() : null)).then(c => c && setCfg(c));
  }, []);

  const mudar = (campo, valor) => setCfg(c => ({ ...c, [campo]: valor }));
  const alternar = (campo, item) => setCfg(c => ({
    ...c, [campo]: c[campo].includes(item) ? c[campo].filter(x => x !== item) : [...c[campo], item],
  }));

  const salvar = async () => {
    setErro('');
    const res = await authFetch(`${API}/relatorios/automatico`, { method: 'PUT', body: JSON.stringify(cfg) }).catch(() => null);
    const r = await res?.json().catch(() => ({}));
    if (!res?.ok) { setErro(r?.detail || 'Não foi possível salvar.'); return; }
    onSalvo(r);
  };

  const chip = (ativo) => `flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold border transition-colors ${ativo
    ? 'bg-emerald-600 border-emerald-500 text-white' : 'bg-slate-950 border-slate-700 text-slate-300 hover:border-slate-500'}`;

  return (
    <div className="fixed inset-0 z-[230] bg-black/60 backdrop-blur-sm flex items-center justify-center p-3" onClick={onFechar}>
      <div className="w-full max-w-md max-h-[90dvh] flex flex-col bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
          <h2 className="text-base font-black text-white">Envio automático</h2>
          <button onClick={onFechar} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10" title="Fechar"><X size={18}/></button>
        </div>
        {!cfg ? <p className="p-5 text-sm text-slate-500">Carregando…</p> : (
          <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-5 space-y-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" checked={cfg.ativo} onChange={e => mudar('ativo', e.target.checked)} className="w-4 h-4 accent-emerald-500"/>
              <span className="text-sm font-bold text-slate-100">Enviar meu relatório do dia automaticamente</span>
            </label>
            <div className={`space-y-4 ${cfg.ativo ? '' : 'opacity-40 pointer-events-none'}`}>
              <div>
                <div className="text-xs font-bold text-slate-400 uppercase mb-1.5">Dias</div>
                <div className="flex flex-wrap gap-1.5">
                  {DIAS.map((d, i) => <button key={d} onClick={() => alternar('dias', i)} className={chip(cfg.dias.includes(i))}>{d}</button>)}
                </div>
              </div>
              <div>
                <div className="text-xs font-bold text-slate-400 uppercase mb-1.5">Horário</div>
                <input type="time" value={cfg.hora} onChange={e => mudar('hora', e.target.value)}
                  className="p-2 bg-slate-950 text-slate-100 border border-slate-700 rounded-lg outline-none focus:border-emerald-500 text-sm"/>
              </div>
              <div>
                <div className="text-xs font-bold text-slate-400 uppercase mb-1.5">Para</div>
                {gestores.length === 0 ? <p className="text-xs text-slate-500">Ninguém tem acesso à Gestão para receber relatórios.</p> : (
                  <div className="flex flex-wrap gap-1.5">
                    {gestores.map(g => (
                      <button key={g.id} onClick={() => alternar('para', g.id)} className={chip(cfg.para.includes(g.id))}>
                        {cfg.para.includes(g.id) && <Check size={12}/>}{g.nome}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <div className="text-xs font-bold text-slate-400 uppercase mb-1.5">Se eu não escrever nada no dia</div>
                {[
                  { val: 'nada', label: 'Não enviar' },
                  { val: 'resumo', label: 'Enviar o resumo do dia gerado pelo Kyndo (cards, etapas e tempo)' },
                ].map(o => (
                  <label key={o.val} className="flex items-start gap-2 py-1 cursor-pointer text-sm text-slate-200">
                    <input type="radio" name="sem_texto" checked={cfg.sem_texto === o.val} onChange={() => mudar('sem_texto', o.val)} className="mt-1 accent-emerald-500"/>
                    {o.label}
                  </label>
                ))}
              </div>
              <p className="text-[11px] text-slate-500">
                Sai o texto como estiver no horário. Se você já tiver enviado o mesmo texto para alguém naquele dia, ele não recebe de novo.
              </p>
            </div>
            {erro && <p className="text-xs font-bold text-red-400">{erro}</p>}
            <button onClick={salvar} className="w-full px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold">Salvar</button>
          </div>
        )}
      </div>
    </div>
  );
}
