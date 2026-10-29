import React, { useEffect, useState } from 'react';
import { Lock, Mail } from 'lucide-react';
import { API, authFetch } from '../api.js';

const CAMPO = 'w-full p-2 bg-slate-900 text-slate-100 border border-slate-700 rounded-lg outline-none focus:border-emerald-500 text-sm';

// Aba "Minha conta" das Configurações — aberta a todos: o próprio e-mail e
// quais avisos receber por e-mail.
export default function MinhaConta({ user }) {
  const [conta, setConta] = useState(null);
  const [editandoEmail, setEditandoEmail] = useState(false);
  const [novoEmail, setNovoEmail] = useState('');
  const [senhaAtual, setSenhaAtual] = useState('');
  const [erro, setErro] = useState('');
  const [aviso, setAviso] = useState('');

  const carregar = () => authFetch(`${API}/me/conta`).then(r => (r.ok ? r.json() : null)).then(setConta);
  useEffect(() => { carregar(); }, []);

  const abrirEdicao = () => {
    setNovoEmail(conta?.email || '');
    setSenhaAtual('');
    setErro('');
    setAviso('');
    setEditandoEmail(true);
  };

  const salvarEmail = async (e) => {
    e.preventDefault();
    setErro('');
    const res = await authFetch(`${API}/users/${user.id}/email`, {
      method: 'PUT', body: JSON.stringify({ email: novoEmail, senha_atual: senhaAtual }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { setErro(data.detail || 'Não foi possível salvar o e-mail.'); return; }
    setEditandoEmail(false);
    setAviso(data.email ? `E-mail salvo: ${data.email}.` : 'E-mail removido.');
    carregar();
  };

  const gravarPreferencias = async (corpo) => {
    const res = await authFetch(`${API}/me/preferencias`, { method: 'PUT', body: JSON.stringify(corpo) });
    if (res.ok) {
      const data = await res.json();
      setConta(c => ({ ...c, preferencias: data.preferencias, entrega: data.entrega }));
    }
  };

  // Avisos agrupados como o servidor manda (Cards, Sugestões, Resumos).
  const grupos = [];
  for (const p of conta?.preferencias || []) {
    let g = grupos.find(x => x.nome === p.grupo);
    if (!g) { g = { nome: p.grupo, itens: [] }; grupos.push(g); }
    g.itens.push(p);
  }

  if (!conta) return <div className="text-sm text-slate-500">Carregando…</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-4">
        <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Mail size={20}/> Meu e-mail</h3>
        <p className="text-xs text-slate-400">É por ele que chegam os avisos e o link de "Esqueci a senha".</p>
        {editandoEmail ? (
          <form onSubmit={salvarEmail} className="space-y-3">
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase mb-1">E-mail</label>
              <input type="email" autoFocus value={novoEmail} onChange={e => setNovoEmail(e.target.value)} placeholder="voce@empresa.com.br" className={CAMPO}/>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Sua senha atual</label>
              <input type="password" value={senhaAtual} onChange={e => setSenhaAtual(e.target.value)} className={CAMPO} required/>
            </div>
            {erro && <p className="text-xs font-bold text-red-400">{erro}</p>}
            <div className="flex items-center gap-3">
              <button type="submit" className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold">Salvar e-mail</button>
              <button type="button" onClick={() => setEditandoEmail(false)} className="text-xs font-bold text-slate-400 hover:text-slate-200">Cancelar</button>
            </div>
            <p className="text-[11px] text-slate-500">Deixe em branco para tirar o e-mail. O endereço antigo recebe um aviso da troca.</p>
          </form>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <span className={`text-sm truncate ${conta.email ? 'text-slate-100 font-bold' : 'text-slate-500 italic'}`}>
              {conta.email || 'Nenhum e-mail cadastrado'}
            </span>
            <button onClick={abrirEdicao} className="shrink-0 text-xs font-bold text-emerald-400 hover:underline">
              {conta.email ? 'Trocar' : 'Cadastrar'}
            </button>
          </div>
        )}
        {aviso && <p className="text-xs font-bold text-emerald-400">{aviso}</p>}
      </div>

      <div className="md:col-span-2 bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-4">
        <div>
          <h3 className="text-lg font-bold text-slate-100">Avisos por e-mail</h3>
          <p className="text-xs text-slate-400 mt-1">
            Para cada aviso, escolha de quais cards quer receber. "Meus cards" são os que você é responsável ou criou;
            "os que sigo" são os que você marcou com <span className="font-bold text-slate-300">Seguir</span> dentro do card.
          </p>
        </div>
        {!conta.email && <p className="text-xs text-amber-300/80">Cadastre um e-mail para receber estes avisos.</p>}
        {!conta.email_ativo && <p className="text-xs text-slate-500">O envio de e-mails ainda não foi configurado no servidor.</p>}

        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-xs font-bold text-slate-400 uppercase mr-1">Como receber</span>
          {[
            { val: 'imediato', label: 'Na hora', dica: 'um e-mail a cada acontecimento' },
            { val: 'resumo', label: `Resumo do dia (${conta.hora_resumo_avisos}h)`, dica: 'tudo junto num e-mail só' },
          ].map(o => (
            <button key={o.val} onClick={() => conta.entrega !== o.val && gravarPreferencias({ entrega: o.val })} title={o.dica}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${conta.entrega === o.val ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-700'}`}>
              {o.label}
            </button>
          ))}
        </div>

        {grupos.map(g => (
          <div key={g.nome} className="space-y-1">
            <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{g.nome}</div>
            {g.itens.map(p => {
              const desligado = p.modo === 'desligado';
              return (
                <div key={p.tipo} className="flex flex-wrap items-center gap-2 py-1 border-b border-slate-700/50 last:border-0">
                  <span className={`flex-1 min-w-[200px] text-sm ${desligado ? 'text-slate-500' : 'text-slate-200'}`}>{p.rotulo}</span>
                  {p.modo === 'obrigatorio' && <span className="flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400" title="Definido como obrigatório pelo administrador: dá para ampliar, não para desligar"><Lock size={10}/> obrigatório</span>}
                  {desligado ? (
                    <span className="w-44 text-center text-[11px] font-bold uppercase text-slate-500">desativado</span>
                  ) : (
                    <select value={p.alcance} onChange={e => gravarPreferencias({ avisos: { [p.tipo]: e.target.value } })}
                      className="w-44 text-xs bg-slate-900 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400">
                      {p.alcances.map(a => (
                        <option key={a.valor} value={a.valor} disabled={p.modo === 'obrigatorio' && a.valor === 'nenhum'}>{a.rotulo}</option>
                      ))}
                    </select>
                  )}
                </div>
              );
            })}
          </div>
        ))}
        <p className="text-[11px] text-slate-500">Os e-mails de segurança (link de nova senha e aviso de senha ou e-mail alterados) sempre chegam.</p>
      </div>
    </div>
  );
}
