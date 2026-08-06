import React, { useEffect, useState } from 'react';
import { User, Users, Trash2, ScrollText, Shield } from 'lucide-react';
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

  const [aba, setAba] = useState(() => (canSeeUsersTab ? 'usuarios' : canViewAuditLog ? 'log' : null));
  const [novoNome, setNovoNome] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [msg, setMsg] = useState('');
  const [rolesDisponiveis, setRolesDisponiveis] = useState([]);
  const [editandoCargosDe, setEditandoCargosDe] = useState(null);
  const [cargosSelecionados, setCargosSelecionados] = useState([]);

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
    await authFetch(`${API}/users/${id}`, { method: 'DELETE' });
    refreshUsers();
  };

  const abrirEdicaoCargos = (u) => {
    setEditandoCargosDe(u.id);
    setCargosSelecionados((u.roles || []).map(r => r.id));
  };

  const salvarCargos = async (userId) => {
    await authFetch(`${API}/users/${userId}/roles`, {
      method: 'PUT',
      body: JSON.stringify({ role_ids: cargosSelecionados }),
    });
    setEditandoCargosDe(null);
    refreshUsers();
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col">
        <div className="bg-emerald-700 p-6 flex justify-between items-center text-white">
          <div>
            <h2 className="text-2xl font-black italic tracking-tighter uppercase">Config</h2>
            <p className="text-emerald-200 text-sm">Usuários, cargos e auditoria</p>
          </div>
          <button onClick={onBack} className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-xl font-bold transition-colors">Voltar ao Quadro</button>
        </div>

        <div className="flex gap-2 px-8 pt-6">
          {canSeeUsersTab && (
            <button onClick={() => setAba('usuarios')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-colors ${aba === 'usuarios' ? 'bg-emerald-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              <Users size={16}/> Usuários
            </button>
          )}
          {canManageRoles && (
            <button onClick={() => setAba('cargos')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-colors ${aba === 'cargos' ? 'bg-emerald-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              <Shield size={16}/> Cargos
            </button>
          )}
          {canViewAuditLog && (
            <button onClick={() => setAba('log')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-colors ${aba === 'log' ? 'bg-emerald-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
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
            <RolesPanel/>
          </div>
        ) : aba === 'usuarios' && canSeeUsersTab ? (
        <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-8">
          {canManageUsers && (
            <div className="bg-gray-50 p-6 rounded-xl border border-gray-200">
              <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2"><User size={20}/> Novo Usuário</h3>
              {msg && <div className="mb-4 text-sm font-bold text-emerald-600 bg-emerald-50 p-2 rounded">{msg}</div>}
              <form onSubmit={criarUsuario} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Nome</label>
                  <input type="text" value={novoNome} onChange={e => setNovoNome(e.target.value)} className="w-full p-2 border rounded-lg outline-none focus:border-emerald-500" required />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Senha Temporária</label>
                  <input type="text" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} className="w-full p-2 border rounded-lg outline-none focus:border-emerald-500" required />
                </div>
                <p className="text-xs text-gray-500">O usuário nasce com o cargo base "Usuário" — atribua outros cargos depois, na lista ao lado.</p>
                <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded-lg transition-colors">Criar Usuário</button>
              </form>
            </div>
          )}

          <div>
            <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2"><Users size={20}/> Usuários Cadastrados</h3>
            <div className="space-y-2">
              {currentUsers.map(u => {
                const isProtected = (u.roles || []).some(r => r.protegido);
                return (
                  <div key={u.id} className="p-3 bg-white border border-gray-200 rounded-xl shadow-sm">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="font-bold text-gray-800">{u.nome}</p>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {(u.roles || []).length === 0 && <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-gray-100 text-gray-600">Sem cargo</span>}
                          {(u.roles || []).map(r => (
                            <span key={r.id} className="text-[10px] font-bold uppercase px-2 py-0.5 rounded text-white" style={{ backgroundColor: r.cor }}>{r.nome}</span>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {canManageRoles && (
                          <button onClick={() => (editandoCargosDe === u.id ? setEditandoCargosDe(null) : abrirEdicaoCargos(u))} className="text-xs font-bold text-emerald-700 hover:underline">
                            {editandoCargosDe === u.id ? 'Cancelar' : 'Cargos'}
                          </button>
                        )}
                        {canDeleteUsers && !isProtected && (
                          <button onClick={() => deletarUsuario(u.id)} className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"><Trash2 size={18}/></button>
                        )}
                      </div>
                    </div>
                    {editandoCargosDe === u.id && (
                      <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
                        {rolesDisponiveis.map(r => (
                          <label key={r.id} className="flex items-center gap-2 text-sm text-gray-700">
                            <input
                              type="checkbox"
                              checked={cargosSelecionados.includes(r.id)}
                              onChange={e => setCargosSelecionados(prev => e.target.checked ? [...prev, r.id] : prev.filter(id => id !== r.id))}
                            />
                            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: r.cor }}/>
                            {r.nome}
                          </label>
                        ))}
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
          <div className="p-8 text-gray-500 text-sm">Você não tem permissão para ver nenhuma seção aqui.</div>
        )}
      </div>
    </div>
  );
}
