import React, { useState } from 'react';
import { User, Users, Trash2 } from 'lucide-react';
import { API, authFetch } from '../api.js';

export default function AdminPanel({ onBack, currentUsers, refreshUsers }) {
  const [novoNome, setNovoNome] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [novoRole, setNovoRole] = useState('user');
  const [msg, setMsg] = useState('');

  const criarUsuario = async (e) => {
    e.preventDefault();
    const res = await authFetch(`${API}/users`, {
      method: 'POST',
      body: JSON.stringify({ nome: novoNome, senha: novaSenha, role: novoRole }),
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

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col">
        <div className="bg-emerald-700 p-6 flex justify-between items-center text-white">
          <div>
            <h2 className="text-2xl font-black italic tracking-tighter uppercase">Painel Admin</h2>
            <p className="text-emerald-200 text-sm">Gerenciamento de Usuários</p>
          </div>
          <button onClick={onBack} className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-xl font-bold transition-colors">Voltar ao Quadro</button>
        </div>

        <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-8">
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
              <div>
                <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Nível de Acesso</label>
                <select value={novoRole} onChange={e => setNovoRole(e.target.value)} className="w-full p-2 border rounded-lg outline-none focus:border-emerald-500">
                  <option value="user">Usuário Padrão</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded-lg transition-colors">Criar Usuário</button>
            </form>
          </div>

          <div>
            <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2"><Users size={20}/> Usuários Cadastrados</h3>
            <div className="space-y-2">
              {currentUsers.map(u => (
                <div key={u.id} className="flex justify-between items-center p-3 bg-white border border-gray-200 rounded-xl shadow-sm">
                  <div>
                    <p className="font-bold text-gray-800">{u.nome}</p>
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${u.role === 'superadmin' ? 'bg-purple-100 text-purple-700' : u.role === 'admin' ? 'bg-orange-100 text-orange-700' : 'bg-gray-100 text-gray-600'}`}>
                      {u.role === 'superadmin' ? 'Super Admin' : u.role === 'admin' ? 'Admin' : 'Usuário'}
                    </span>
                  </div>
                  {u.role !== 'superadmin' && (
                    <button onClick={() => deletarUsuario(u.id)} className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"><Trash2 size={18}/></button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
