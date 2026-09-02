import React, { useState } from 'react';
import { KeyRound } from 'lucide-react';
import { API, authFetch } from '../api.js';

export default function ChangePasswordScreen({ user, onPasswordChanged }) {
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmarSenha, setConfirmarSenha] = useState('');
  const [erro, setErro] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (novaSenha !== confirmarSenha) { setErro('As senhas digitadas não coincidem.'); return; }
    if (novaSenha.length < 4) { setErro('A senha deve ter pelo menos 4 caracteres.'); return; }

    try {
      const res = await authFetch(`${API}/users/${user.id}/password`, {
        method: 'PUT',
        body: JSON.stringify({ nova_senha: novaSenha }),
      });
      if (res.ok) { onPasswordChanged(); }
      else { setErro('Erro ao alterar a senha.'); }
    } catch {
      setErro('Erro de conexão.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex justify-center mb-4"><KeyRound size={48} className="text-orange-400" /></div>
        <h2 className="text-2xl font-black text-slate-100 text-center mb-2">Quase lá, {user.nome}!</h2>
        <p className="text-slate-400 text-center mb-6 text-sm">Você está usando uma senha temporária. Por favor, crie uma nova senha de segurança para continuar.</p>

        {erro && <div className="bg-red-500/10 text-red-400 border border-red-500/20 p-3 rounded-lg mb-4 text-sm font-bold text-center">{erro}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Nova Senha</label>
            <input type="password" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} className="w-full p-3 bg-slate-800 text-slate-100 border border-slate-700 rounded-xl outline-none focus:border-orange-500" required />
          </div>
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Confirmar Nova Senha</label>
            <input type="password" value={confirmarSenha} onChange={e => setConfirmarSenha(e.target.value)} className="w-full p-3 bg-slate-800 text-slate-100 border border-slate-700 rounded-xl outline-none focus:border-orange-500" required />
          </div>
          <button type="submit" className="w-full bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 rounded-xl transition-colors shadow-lg mt-4">
            Salvar e Entrar
          </button>
        </form>
      </div>
    </div>
  );
}
