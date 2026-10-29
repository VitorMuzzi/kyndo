import React, { useState } from 'react';
import { API } from '../api.js';
import { APP_VERSION } from '../constants.jsx';

const CAMPO = 'w-full p-3 bg-slate-800 text-slate-100 border border-slate-700 rounded-xl outline-none focus:border-emerald-500';
const ROTULO = 'block text-xs font-bold text-slate-400 uppercase mb-1';
const LINK = 'w-full text-xs font-bold text-slate-400 hover:text-emerald-300 transition-colors';

// fetch puro, não authFetch: aqui ainda não há sessão (e um 401 não deve recarregar a página).
const enviar = (url, body, { metodo = 'POST', token } = {}) => fetch(url, {
  method: metodo,
  headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
  body: JSON.stringify(body),
});

export default function LoginScreen({ onLogin }) {
  const [nome, setNome] = useState('');
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState('');
  // 'login' | 'esqueci' | 'trocar' | 'redefinir' (link do e-mail, ?redefinir=token)
  const [tokenRedefinir] = useState(() => new URLSearchParams(window.location.search).get('redefinir'));
  const [modo, setModo] = useState(() => (tokenRedefinir ? 'redefinir' : 'login'));
  const [aviso, setAviso] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmarSenha, setConfirmarSenha] = useState('');

  const irPara = (novoModo) => {
    setModo(novoModo); setAviso(''); setErro(''); setSenha(''); setNovaSenha(''); setConfirmarSenha('');
  };

  const pedirNovaSenha = async (e) => {
    e.preventDefault();
    setErro('');
    try {
      const res = await enviar(`${API}/esqueci-senha`, { nome });
      const data = await res.json().catch(() => ({}));
      if (res.ok) setAviso(data.msg);
      else setErro(data.detail || 'Não foi possível registrar o pedido.');
    } catch {
      setErro('Erro ao conectar com o servidor.');
    }
  };

  const redefinirSenha = async (e) => {
    e.preventDefault();
    setErro('');
    if (novaSenha !== confirmarSenha) { setErro('As senhas novas não coincidem.'); return; }
    if (novaSenha.length < 4) { setErro('A senha deve ter pelo menos 4 caracteres.'); return; }
    try {
      const res = await enviar(`${API}/redefinir-senha`, { token: tokenRedefinir, nova_senha: novaSenha });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { setErro(data.detail || 'Não foi possível redefinir a senha.'); return; }
      // Tira o token da barra de endereço: ele já foi usado.
      window.history.replaceState(null, '', window.location.pathname);
      irPara('login');
      setAviso(data.msg);
    } catch {
      setErro('Erro ao conectar com o servidor.');
    }
  };

  // Trocar a senha sem entrar no quadro: confere usuário e senha atual pelo
  // login e usa esse token só para a troca — a pessoa entra depois, com a nova.
  const trocarSenha = async (e) => {
    e.preventDefault();
    setErro('');
    if (novaSenha !== confirmarSenha) { setErro('As senhas novas não coincidem.'); return; }
    if (novaSenha.length < 4) { setErro('A senha deve ter pelo menos 4 caracteres.'); return; }
    try {
      const login = await enviar(`${API}/login`, { nome, senha });
      if (!login.ok) { setErro('Usuário ou senha atual incorretos.'); return; }
      const { id, token } = await login.json();
      const res = await enviar(`${API}/users/${id}/password`, { nova_senha: novaSenha, senha_atual: senha }, { metodo: 'PUT', token });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { setErro(data.detail || 'Não foi possível trocar a senha.'); return; }
      irPara('login');
      setAviso('Senha trocada. Entre com a nova senha.');
    } catch {
      setErro('Erro ao conectar com o servidor.');
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await enviar(`${API}/login`, { nome, senha });
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
        <p className="text-slate-400 text-center mb-8 text-sm">
          {modo === 'trocar' ? 'Trocar senha' : modo === 'esqueci' ? 'Esqueci a senha' : modo === 'redefinir' ? 'Criar nova senha' : 'Acesse o quadro de tarefas'}
        </p>

        {erro && <div className="bg-red-500/10 text-red-400 border border-red-500/20 p-3 rounded-lg mb-4 text-sm font-bold text-center">{erro}</div>}
        {aviso && <div className="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 p-3 rounded-lg mb-4 text-sm text-center">{aviso}</div>}

        {modo === 'esqueci' ? (
          aviso ? (
            <button onClick={() => irPara('login')} className="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3 rounded-xl transition-colors">Voltar ao login</button>
          ) : (
            <form onSubmit={pedirNovaSenha} className="space-y-4">
              <p className="text-sm text-slate-400">Digite seu usuário ou e-mail. Se você tiver e-mail cadastrado, chega um link para criar uma nova senha; senão, um administrador recebe o pedido.</p>
              <div>
                <label className={ROTULO}>Usuário ou e-mail</label>
                <input type="text" autoFocus value={nome} onChange={e => setNome(e.target.value)} className={CAMPO} required />
              </div>
              <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl transition-colors shadow-lg">Pedir nova senha</button>
              <button type="button" onClick={() => irPara('login')} className={LINK}>Voltar ao login</button>
            </form>
          )
        ) : modo === 'redefinir' ? (
          <form onSubmit={redefinirSenha} className="space-y-4">
            <div>
              <label className={ROTULO}>Nova senha</label>
              <input type="password" autoFocus value={novaSenha} onChange={e => setNovaSenha(e.target.value)} className={CAMPO} required />
            </div>
            <div>
              <label className={ROTULO}>Confirmar nova senha</label>
              <input type="password" value={confirmarSenha} onChange={e => setConfirmarSenha(e.target.value)} className={CAMPO} required />
            </div>
            <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl transition-colors shadow-lg mt-4">Salvar nova senha</button>
            <button type="button" onClick={() => { window.history.replaceState(null, '', window.location.pathname); irPara('login'); }} className={LINK}>Voltar ao login</button>
          </form>
        ) : modo === 'trocar' ? (
          <form onSubmit={trocarSenha} className="space-y-4">
            <div>
              <label className={ROTULO}>Usuário</label>
              <input type="text" value={nome} onChange={e => setNome(e.target.value)} className={CAMPO} required />
            </div>
            <div>
              <label className={ROTULO}>Senha atual</label>
              <input type="password" autoFocus value={senha} onChange={e => setSenha(e.target.value)} className={CAMPO} required />
            </div>
            <div>
              <label className={ROTULO}>Nova senha</label>
              <input type="password" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} className={CAMPO} required />
            </div>
            <div>
              <label className={ROTULO}>Confirmar nova senha</label>
              <input type="password" value={confirmarSenha} onChange={e => setConfirmarSenha(e.target.value)} className={CAMPO} required />
            </div>
            <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl transition-colors shadow-lg mt-4">Trocar senha</button>
            <button type="button" onClick={() => irPara('login')} className={LINK}>Voltar ao login</button>
          </form>
        ) : (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className={ROTULO}>Usuário</label>
              <input type="text" value={nome} onChange={e => setNome(e.target.value)} className={CAMPO} required />
            </div>
            <div>
              <label className={ROTULO}>Senha</label>
              <input type="password" value={senha} onChange={e => setSenha(e.target.value)} className={CAMPO} required />
            </div>
            <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl transition-colors shadow-lg mt-4">
              Entrar
            </button>
            <div className="flex justify-between gap-4">
              <button type="button" onClick={() => irPara('esqueci')} className="text-xs font-bold text-slate-400 hover:text-emerald-300 transition-colors">
                Esqueci a senha
              </button>
              <button type="button" onClick={() => irPara('trocar')} className="text-xs font-bold text-slate-400 hover:text-emerald-300 transition-colors">
                Trocar senha
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
