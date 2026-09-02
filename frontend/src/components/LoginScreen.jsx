import React, { useState } from 'react';
import { API } from '../api.js';
import { APP_VERSION } from '../constants.jsx';

export default function LoginScreen({ onLogin }) {
  const [nome, setNome] = useState('');
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome, senha }),
      });
      if (res.ok) {
        onLogin(await res.json());
      } else {
        setErro('Usuário ou senha incorretos.');
      }
    } catch {
      setErro('Erro ao conectar com o servidor.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <span className="fixed bottom-1.5 right-2 text-[9px] text-white/20 font-mono pointer-events-none select-none">{APP_VERSION}</span>
      <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl w-full max-w-md">
        <h1 className="text-3xl font-black text-emerald-400 italic tracking-tighter uppercase mb-2 text-center">Kyndo</h1>
        <p className="text-slate-400 text-center mb-8 text-sm">Acesse o quadro de tarefas</p>

        {erro && <div className="bg-red-500/10 text-red-400 border border-red-500/20 p-3 rounded-lg mb-4 text-sm font-bold text-center">{erro}</div>}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Usuário</label>
            <input type="text" value={nome} onChange={e => setNome(e.target.value)} className="w-full p-3 bg-slate-800 text-slate-100 border border-slate-700 rounded-xl outline-none focus:border-emerald-500" required />
          </div>
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase mb-1">Senha</label>
            <input type="password" value={senha} onChange={e => setSenha(e.target.value)} className="w-full p-3 bg-slate-800 text-slate-100 border border-slate-700 rounded-xl outline-none focus:border-emerald-500" required />
          </div>
          <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl transition-colors shadow-lg mt-4">
            Entrar
          </button>
        </form>
      </div>
    </div>
  );
}
