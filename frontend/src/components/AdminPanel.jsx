import React, { useEffect, useState } from 'react';
import { User, Users, Trash2, ScrollText, Shield, Lock } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { hasPermission } from '../constants.jsx';
import AuditLogPanel from './AuditLogPanel.jsx';
import RolesPanel from './RolesPanel.jsx';

export default function AdminPanel({ user, onBack, currentUsers, refreshUsers }) {
  const canManageUsers = hasPermission(user, 'gerenciar_usuarios');
  const canDeleteUsers = hasPermission(user, 'excluir_usuarios');
  const canManageRoles = hasPermission(user, 'gerenciar_cargos');
  const canViewAuditLog = hasPermission(user, 'ver_log_auditoria');
  // Seeing the user list only makes sense if you can act on it somehow —
  // create/delete a user, or assign cargos (which needs to see who's who).
  const canSeeUsersTab = canManageUsers || canDeleteUsers || canManageRoles;
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
  const [editandoCargosDe, setEditandoCargosDe] = useState(null);
  const [cargosSelecionados, setCargosSelecionados] = useState([]);
  const [erroCargos, setErroCargos] = useState('');

  useEffect(() => {
    if (canManageRoles) authFetch(`${API}/roles`).then(r => (r.ok ? r.json() : [])).then(setRolesDisponiveis);
  }, [canManageRoles]);

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

  const abrirEdicaoCargos = (u) => {
    setErroCargos('');
    setEditandoCargosDe(u.id);
    setCargosSelecionados((u.roles || []).map(r => r.id));
  };

  const salvarCargos = async (userId) => {
    const res = await authFetch(`${API}/users/${userId}/roles`, {
      method: 'PUT',
      body: JSON.stringify({ role_ids: cargosSelecionados }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setErroCargos(data.detail || 'Não foi possível salvar os cargos.');
      return;
    }
    setEditandoCargosDe(null);
    refreshUsers();
  };

  return (
    <div className="min-h-screen bg-slate-950 p-8">
      <div className="max-w-4xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden flex flex-col">
        <div className="bg-gradient-to-r from-emerald-700 to-teal-700 p-6 flex justify-between items-center text-white">
          <div>
            <h2 className="text-2xl font-black italic tracking-tighter uppercase">Config</h2>
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
                return (
                  <div key={u.id} className="p-3 bg-slate-800 border border-slate-700 rounded-xl shadow-sm">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="font-bold text-slate-100">{u.nome}</p>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {(u.roles || []).length === 0 && <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-slate-700 text-slate-300">Sem cargo</span>}
                          {(u.roles || []).map(r => (
                            <span key={r.id} className="text-[10px] font-bold uppercase px-2 py-0.5 rounded text-white" style={{ backgroundColor: r.cor }}>{r.nome}</span>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {canManageRoles && (u.id !== user.id || souSuperadmin) && (
                          <button onClick={() => (editandoCargosDe === u.id ? setEditandoCargosDe(null) : abrirEdicaoCargos(u))} className="text-xs font-bold text-emerald-400 hover:underline">
                            {editandoCargosDe === u.id ? 'Cancelar' : 'Cargos'}
                          </button>
                        )}
                        {canManageRoles && u.id === user.id && !souSuperadmin && (
                          <span className="text-[10px] text-slate-500" title="Seus cargos só podem ser mudados por outra pessoa">seus cargos</span>
                        )}
                        {canDeleteUsers && !isProtected && (
                          <button onClick={() => deletarUsuario(u.id)} className="p-2 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"><Trash2 size={18}/></button>
                        )}
                      </div>
                    </div>
                    {editandoCargosDe === u.id && (
                      <div className="mt-3 pt-3 border-t border-slate-700 space-y-2">
                        {rolesDisponiveis.map(r => {
                          const bloqueado = !possoRepassar(r);
                          return (
                            <label key={r.id} className={`flex items-center gap-2 text-sm ${bloqueado ? 'text-slate-500' : 'text-slate-300'}`}
                              title={bloqueado ? 'Este cargo tem permissões que você não tem — não dá para você dar nem tirar' : undefined}>
                              <input
                                type="checkbox"
                                disabled={bloqueado}
                                checked={cargosSelecionados.includes(r.id)}
                                onChange={e => setCargosSelecionados(prev => e.target.checked ? [...prev, r.id] : prev.filter(id => id !== r.id))}
                              />
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: r.cor }}/>
                              {r.nome}
                              {bloqueado && <Lock size={11} className="text-slate-600"/>}
                            </label>
                          );
                        })}
                        {erroCargos && <p className="text-xs font-bold text-red-400">{erroCargos}</p>}
                        <button onClick={() => salvarCargos(u.id)} className="mt-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold">Salvar cargos</button>
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
