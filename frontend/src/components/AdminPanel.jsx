import React, { useEffect, useState } from 'react';
import { User, Users, Trash2, ScrollText, Shield, Lock, KeyRound, MoreHorizontal, ChevronDown, Pencil } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { hasPermission } from '../constants.jsx';
import AuditLogPanel from './AuditLogPanel.jsx';
import RolesPanel from './RolesPanel.jsx';

// Campo de seleção dos cargos de um usuário: mostra os que ele tem e, ao
// abrir, todos os cargos com caixinha. Cada clique já salva (o servidor
// confere as travas e o erro aparece aqui mesmo).
function SeletorCargos({ usuario, roles, possoRepassar, travado, onSalvo }) {
  const [aberto, setAberto] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState('');
  const atuais = usuario.roles || [];
  const ids = atuais.map(r => r.id);

  const alternar = async (roleId) => {
    setSalvando(true);
    setErro('');
    const novos = ids.includes(roleId) ? ids.filter(id => id !== roleId) : [...ids, roleId];
    const res = await authFetch(`${API}/users/${usuario.id}/roles`, { method: 'PUT', body: JSON.stringify({ role_ids: novos }) });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setErro(data.detail || 'Não foi possível salvar os cargos.');
    }
    await onSalvo();
    setSalvando(false);
  };

  const rotulo = atuais.length === 0 ? 'Sem cargo' : atuais.map(r => r.nome).join(', ');
  return (
    <div className="relative w-28 sm:w-32 shrink-0">
      <button
        type="button"
        disabled={travado}
        onClick={() => { setErro(''); setAberto(v => !v); }}
        title={travado ? 'Seus cargos só podem ser mudados por outra pessoa' : rotulo}
        className={`w-full flex items-center gap-1.5 px-2 py-1 rounded-lg border text-xs font-bold transition-colors ${travado
          ? 'border-slate-700 bg-slate-800/60 text-slate-400 cursor-default'
          : 'border-slate-600 bg-slate-900 text-slate-200 hover:border-emerald-500'}`}>
        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: atuais[0]?.cor || '#64748b' }}/>
        <span className="truncate flex-1 text-left">{rotulo}</span>
        {travado ? <Lock size={12} className="shrink-0"/> : <ChevronDown size={14} className={`shrink-0 transition-transform ${aberto ? 'rotate-180' : ''}`}/>}
      </button>
      {aberto && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAberto(false)}/>
          <div className="absolute right-0 top-full mt-1 w-60 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-50 p-1.5">
            {roles.map(r => {
              const bloqueado = !possoRepassar(r);
              return (
                <label key={r.id}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm ${bloqueado ? 'text-slate-500' : 'text-slate-200 hover:bg-white/5 cursor-pointer'}`}
                  title={bloqueado ? 'Este cargo tem permissões que você não tem — não dá para você dar nem tirar' : undefined}>
                  <input type="checkbox" disabled={bloqueado || salvando} checked={ids.includes(r.id)} onChange={() => alternar(r.id)}/>
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: r.cor }}/>
                  <span className="flex-1 truncate">{r.nome}</span>
                  {bloqueado && <Lock size={11} className="text-slate-600 shrink-0"/>}
                </label>
              );
            })}
            {erro && <p className="px-2 py-1 text-xs font-bold text-red-400">{erro}</p>}
          </div>
        </>
      )}
    </div>
  );
}

function MenuAcoes({ itens }) {
  const [aberto, setAberto] = useState(false);
  if (itens.length === 0) return <span className="w-6 shrink-0"/>;
  return (
    <div className="relative shrink-0">
      <button type="button" onClick={() => setAberto(v => !v)} title="Mais ações"
        className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-white/10 transition-colors">
        <MoreHorizontal size={16}/>
      </button>
      {aberto && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAberto(false)}/>
          <div className="absolute right-0 top-full mt-1 min-w-[170px] bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-50 overflow-hidden">
            {itens.map(item => (
              <button key={item.rotulo} type="button" onClick={() => { setAberto(false); item.acao(); }}
                className={`w-full flex items-center gap-2 px-4 py-2.5 text-sm font-bold transition-colors ${item.perigo
                  ? 'text-red-400 hover:bg-red-500/10' : 'text-slate-200 hover:bg-emerald-500/10'}`}>
                <item.icone size={14}/> {item.rotulo}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function AdminPanel({ user, onBack, currentUsers, refreshUsers }) {
  const canManageUsers = hasPermission(user, 'gerenciar_usuarios');
  const canDeleteUsers = hasPermission(user, 'excluir_usuarios');
  const canManageRoles = hasPermission(user, 'gerenciar_cargos');
  const canViewAuditLog = hasPermission(user, 'ver_log_auditoria');
  const canChangePasswords = hasPermission(user, 'trocar_senha_outros');
  // Seeing the user list only makes sense if you can act on it somehow —
  // create/delete/rename a user, reset a password, or assign cargos.
  const canSeeUsersTab = canManageUsers || canDeleteUsers || canManageRoles || canChangePasswords;
  // Quem gerencia cargos não mexe no próprio acesso e só repassa o que tem
  // (o servidor confere). O Superadmin fica de fora dessas travas.
  const eu = currentUsers.find(u => u.id === user.id);
  const meusCargos = (eu?.roles || []).map(r => r.id);
  const souSuperadmin = user.role === 'superadmin' || (eu?.roles || []).some(r => r.protegido);
  const possoRepassar = (role) => souSuperadmin
    || Object.entries(role.permissoes || {}).every(([k, v]) => !v || hasPermission(user, k));

  const [aba, setAba] = useState(() => (canSeeUsersTab ? 'usuarios' : canViewAuditLog ? 'log' : null));
  const [novoNome, setNovoNome] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [msg, setMsg] = useState('');
  const [rolesDisponiveis, setRolesDisponiveis] = useState([]);
  // Renomear / definir senha temporária: um painel aberto por vez, embaixo do usuário.
  const [editando, setEditando] = useState(null);  // { id, tipo: 'nome' | 'senha' }
  const [valorEdicao, setValorEdicao] = useState('');
  const [erroEdicao, setErroEdicao] = useState('');
  const [senhaDefinida, setSenhaDefinida] = useState(null);  // { nome, senha } para mostrar depois de salvar
  const [pedidosSenha, setPedidosSenha] = useState([]);

  useEffect(() => {
    if (canManageRoles) authFetch(`${API}/roles`).then(r => (r.ok ? r.json() : [])).then(setRolesDisponiveis);
  }, [canManageRoles]);

  const carregarPedidos = () => {
    if (canChangePasswords) authFetch(`${API}/pedidos-senha`).then(r => (r.ok ? r.json() : [])).then(setPedidosSenha);
  };
  useEffect(carregarPedidos, [canChangePasswords]);

  const gerarSenha = () => {
    // Sem caracteres que se confundem (0/O, 1/l/I) — a pessoa vai digitar o que ouviu.
    const letras = 'abcdefghjkmnpqrstuvwxyz23456789';
    const bytes = crypto.getRandomValues(new Uint8Array(8));
    return Array.from(bytes, b => letras[b % letras.length]).join('');
  };

  const abrirEdicao = (u, tipo) => {
    if (editando?.id === u.id && editando.tipo === tipo) { setEditando(null); return; }
    setErroEdicao('');
    setSenhaDefinida(null);
    setEditando({ id: u.id, tipo });
    setValorEdicao(tipo === 'nome' ? u.nome : gerarSenha());
  };

  const salvarEdicao = async (u) => {
    setErroEdicao('');
    const res = editando.tipo === 'nome'
      ? await authFetch(`${API}/users/${u.id}`, { method: 'PUT', body: JSON.stringify({ nome: valorEdicao }) })
      : await authFetch(`${API}/users/${u.id}/password`, { method: 'PUT', body: JSON.stringify({ nova_senha: valorEdicao }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { setErroEdicao(data.detail || 'Não foi possível salvar.'); return; }
    if (editando.tipo === 'senha') { setSenhaDefinida({ nome: u.nome, senha: valorEdicao }); carregarPedidos(); }
    setEditando(null);
    refreshUsers();
  };

  const descartarPedido = async (pedido) => {
    await authFetch(`${API}/pedidos-senha/${pedido.id}`, { method: 'DELETE' });
    carregarPedidos();
  };

  const criarUsuario = async (e) => {
    e.preventDefault();
    const res = await authFetch(`${API}/users`, {
      method: 'POST',
      body: JSON.stringify({ nome: novoNome, senha: novaSenha }),
    });
    if (res.ok) {
      setNovoNome(''); setNovaSenha(''); setMsg('Usuário criado com sucesso!');
      refreshUsers();
      setTimeout(() => setMsg(''), 3000);
    } else {
      const data = await res.json();
      setMsg(`Erro: ${data.detail}`);
    }
  };

  const deletarUsuario = async (id) => {
    if (!window.confirm('Certeza que deseja excluir este usuário?')) return;
    const res = await authFetch(`${API}/users/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setMsg(`Erro: ${data.detail || 'não foi possível excluir'}`);
    }
    refreshUsers();
  };

  return (
    <div className="min-h-screen bg-slate-950 p-8">
      <div className="max-w-4xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl shadow-xl flex flex-col">
        <div className="bg-gradient-to-r from-emerald-700 to-teal-700 rounded-t-2xl p-6 flex justify-between items-center text-white">
          <div>
            <h2 className="text-2xl font-black italic tracking-tighter uppercase">Configurações</h2>
            <p className="text-emerald-200 text-sm">Usuários, cargos e auditoria</p>
          </div>
          <button onClick={onBack} className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-xl font-bold transition-colors">Voltar ao Quadro</button>
        </div>

        <div className="flex gap-2 px-8 pt-6">
          {canSeeUsersTab && (
            <button onClick={() => setAba('usuarios')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-colors ${aba === 'usuarios' ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
              <Users size={16}/> Usuários
            </button>
          )}
          {canManageRoles && (
            <button onClick={() => setAba('cargos')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-colors ${aba === 'cargos' ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
              <Shield size={16}/> Cargos
            </button>
          )}
          {canViewAuditLog && (
            <button onClick={() => setAba('log')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-colors ${aba === 'log' ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
              <ScrollText size={16}/> Log de Auditoria
            </button>
          )}
        </div>

        {aba === 'log' && canViewAuditLog ? (
          <div className="p-8">
            <AuditLogPanel/>
          </div>
        ) : aba === 'cargos' && canManageRoles ? (
          <div className="p-8">
            <RolesPanel user={user} meusCargos={meusCargos} souSuperadmin={souSuperadmin}/>
          </div>
        ) : aba === 'usuarios' && canSeeUsersTab ? (
        <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-8">
          {(pedidosSenha.length > 0 || senhaDefinida) && (
            <div className="md:col-span-2 space-y-3">
              {senhaDefinida && (
                <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-sm text-emerald-200 flex flex-wrap items-center gap-2">
                  <KeyRound size={16} className="shrink-0"/>
                  <span>Senha temporária de <b>{senhaDefinida.nome}</b>:</span>
                  <code className="px-2 py-0.5 rounded bg-slate-900 text-emerald-300 font-mono select-all">{senhaDefinida.senha}</code>
                  <span className="text-emerald-200/70">— passe para a pessoa; ela cria uma nova no próximo login.</span>
                  <button onClick={() => setSenhaDefinida(null)} className="ml-auto text-xs font-bold text-emerald-300 hover:underline">OK</button>
                </div>
              )}
              {pedidosSenha.length > 0 && (
                <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10">
                  <h3 className="text-sm font-black text-amber-300 mb-1 flex items-center gap-2"><KeyRound size={16}/> Pedidos de nova senha</h3>
                  <p className="text-xs text-amber-200/70 mb-3">Confirme com a pessoa que o pedido é dela antes de definir a senha.</p>
                  <div className="space-y-2">
                    {pedidosSenha.map(p => {
                      const alvo = currentUsers.find(u => u.id === p.user_id);
                      return (
                        <div key={p.id} className="flex flex-wrap items-center gap-3 text-sm">
                          <span className="font-bold text-slate-100">{p.nome}</span>
                          <span className="text-xs text-slate-400">pediu em {new Date(p.criado_em).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</span>
                          <div className="ml-auto flex gap-3">
                            {alvo && <button onClick={() => abrirEdicao(alvo, 'senha')} className="text-xs font-bold text-emerald-400 hover:underline">Definir senha</button>}
                            <button onClick={() => descartarPedido(p)} className="text-xs font-bold text-slate-400 hover:underline">Descartar</button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
          {canManageUsers && (
            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700">
              <h3 className="text-lg font-bold text-slate-100 mb-4 flex items-center gap-2"><User size={20}/> Novo Usuário</h3>
              {msg && <div className="mb-4 text-sm font-bold text-emerald-400 bg-emerald-500/10 p-2 rounded">{msg}</div>}
              <form onSubmit={criarUsuario} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Nome</label>
                  <input type="text" value={novoNome} onChange={e => setNovoNome(e.target.value)} className="w-full p-2 bg-slate-900 text-slate-100 border border-slate-700 rounded-lg outline-none focus:border-emerald-500" required />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Senha Temporária</label>
                  <input type="text" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} className="w-full p-2 bg-slate-900 text-slate-100 border border-slate-700 rounded-lg outline-none focus:border-emerald-500" required />
                </div>
                <p className="text-xs text-slate-500">O usuário nasce com o cargo base "Usuário" — atribua outros cargos depois, na lista ao lado.</p>
                <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded-lg transition-colors">Criar Usuário</button>
              </form>
            </div>
          )}

          <div>
            <h3 className="text-lg font-bold text-slate-100 mb-4 flex items-center gap-2"><Users size={20}/> Usuários Cadastrados</h3>
            <div className="space-y-2">
              {currentUsers.map(u => {
                const isProtected = (u.roles || []).some(r => r.protegido);
                // Mesmas travas do servidor: a conta admin não muda de nome, e
                // Superadmin só é renomeado ou tem a senha trocada por outro Superadmin.
                const podeRenomear = canManageUsers && u.nome !== 'admin' && (!isProtected || souSuperadmin);
                const podeTrocarSenha = canChangePasswords && u.id !== user.id && (!isProtected || souSuperadmin);
                const aberto = editando?.id === u.id ? editando.tipo : null;
                const acoes = [
                  podeTrocarSenha && { rotulo: 'Definir senha', icone: KeyRound, acao: () => abrirEdicao(u, 'senha') },
                  podeRenomear && { rotulo: 'Renomear', icone: Pencil, acao: () => abrirEdicao(u, 'nome') },
                  canDeleteUsers && !isProtected && u.id !== user.id && { rotulo: 'Excluir', icone: Trash2, perigo: true, acao: () => deletarUsuario(u.id) },
                ].filter(Boolean);
                return (
                  <div key={u.id} className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl shadow-sm">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-bold text-slate-100 truncate">{u.nome}</p>
                        {!canManageRoles && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {(u.roles || []).length === 0 && <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-slate-700 text-slate-300">Sem cargo</span>}
                            {(u.roles || []).map(r => (
                              <span key={r.id} className="text-[10px] font-bold uppercase px-2 py-0.5 rounded text-white" style={{ backgroundColor: r.cor }}>{r.nome}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      {canManageRoles && (
                        <SeletorCargos usuario={u} roles={rolesDisponiveis} possoRepassar={possoRepassar}
                          travado={u.id === user.id && !souSuperadmin} onSalvo={refreshUsers}/>
                      )}
                      <MenuAcoes itens={acoes}/>
                    </div>
                    {aberto && (
                      <div className="mt-3 pt-3 border-t border-slate-700 space-y-2">
                        <label className="block text-xs font-bold text-slate-400 uppercase">
                          {aberto === 'nome' ? 'Novo nome' : 'Senha temporária'}
                        </label>
                        <div className="flex gap-2">
                          <input type="text" autoFocus value={valorEdicao} onChange={e => setValorEdicao(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') salvarEdicao(u); }}
                            className={`flex-1 min-w-0 p-2 bg-slate-900 text-slate-100 border border-slate-700 rounded-lg outline-none focus:border-emerald-500 text-sm ${aberto === 'senha' ? 'font-mono' : ''}`}/>
                          {aberto === 'senha' && (
                            <button onClick={() => setValorEdicao(gerarSenha())} className="px-2 text-xs font-bold text-slate-400 hover:text-slate-200" title="Gerar outra">Gerar</button>
                          )}
                        </div>
                        <p className="text-xs text-slate-500">
                          {aberto === 'nome'
                            ? 'O nome muda em todo o histórico (cards, comentários, tempo, auditoria) e passa a ser o usuário do login.'
                            : 'A pessoa entra com esta senha e é obrigada a criar uma nova. As sessões abertas dela são encerradas.'}
                        </p>
                        {erroEdicao && <p className="text-xs font-bold text-red-400">{erroEdicao}</p>}
                        <div className="flex items-center gap-3">
                          <button onClick={() => salvarEdicao(u)} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold">
                            {aberto === 'nome' ? 'Salvar nome' : 'Definir senha'}
                          </button>
                          <button onClick={() => setEditando(null)} className="text-xs font-bold text-slate-400 hover:text-slate-200">Cancelar</button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        ) : (
          <div className="p-8 text-slate-500 text-sm">Você não tem permissão para ver nenhuma seção aqui.</div>
        )}
      </div>
    </div>
  );
}
