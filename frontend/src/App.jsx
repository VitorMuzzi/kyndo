import React, { useState, useEffect, useRef } from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { Plus, X, AlignLeft, MoreHorizontal, Archive, Palette, CheckSquare, Circle, CheckCircle2, User, Lock, Unlock, Tag, MessageSquare, Filter, Send, Settings, Calendar, RefreshCw, LogOut, Users, Trash2, KeyRound, ChevronDown, ChevronLeft, ChevronRight, Maximize2, Minimize2 } from 'lucide-react';

const API = `http://${window.location.hostname}:8095`;

const GitHubIcon = ({ size = 20, className = '' }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" className={className} aria-hidden="true">
    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
  </svg>
);

function renderTextWithLinks(text) {
  if (!text) return null;
  const parts = text.split(/(https?:\/\/[^\s]+|www\.[^\s]+)/g);
  return parts.map((part, i) => {
    if (/^(https?:\/\/|www\.)/.test(part)) {
      const href = part.startsWith('www.') ? `https://${part}` : part;
      return <a key={i} href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline break-all">{part}</a>;
    }
    return part;
  });
}

const USER_COLORS = [
  'bg-blue-100 text-blue-700',
  'bg-purple-100 text-purple-700',
  'bg-orange-100 text-orange-700',
  'bg-pink-100 text-pink-700',
  'bg-teal-100 text-teal-700',
  'bg-yellow-100 text-yellow-800',
  'bg-red-100 text-red-700',
  'bg-indigo-100 text-indigo-700',
];

const userColor = (nome = '') => {
  let hash = 0;
  for (const c of nome) hash += c.charCodeAt(0);
  return USER_COLORS[hash % USER_COLORS.length];
};

// Auth wrapper
const authFetch = (url, options = {}) => {
  const token = localStorage.getItem('demandaflow_token');
  const headers = { ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!headers['Content-Type'] && options.method !== 'GET') headers['Content-Type'] = 'application/json';
  
  return fetch(url, { ...options, headers }).then(res => {
    if (res.status === 401) {
      localStorage.removeItem('demandaflow_user');
      localStorage.removeItem('demandaflow_token');
      window.location.reload();
    }
    return res;
  });
};

const PRIORIDADES_BADGE = { 'Baixa': 'bg-green-600 text-white shadow-sm', 'Normal': 'bg-yellow-400 text-gray-900 shadow-sm', 'Alta': 'bg-orange-500 text-white shadow-sm', 'Urgente': 'bg-red-600 text-white font-black shadow-sm' };
const PRIORIDADE_CARD_STYLE = { 'Baixa': 'bg-green-100 border-green-500 border-2', 'Normal': 'bg-yellow-50 border-yellow-400 border-2', 'Alta': 'bg-orange-100 border-orange-500 border-2', 'Urgente': 'bg-red-200 border-red-600 border-2 shadow-md shadow-red-300/50' };
const PRIORIDADE_ORDEM = { 'Urgente': 4, 'Alta': 3, 'Normal': 2, 'Baixa': 1 };

function formatarData(dataISO) {
  if (!dataISO) return ''; const [ano, mes, dia] = dataISO.split('-'); return `${dia}/${mes}/${ano}`;
}

// Login Screen
function LoginScreen({ onLogin }) {
  const [nome, setNome] = useState('');
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome, senha })
      });
      if (res.ok) {
        const user = await res.json();
        onLogin(user);
      } else {
        setErro('Usuário ou senha incorretos.');
      }
    } catch (err) {
      setErro('Erro ao conectar com o servidor.');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-800 to-teal-900 flex items-center justify-center p-4">
      <div className="bg-white p-8 rounded-2xl shadow-2xl w-full max-w-md">
        <h1 className="text-3xl font-black text-emerald-700 italic tracking-tighter uppercase mb-2 text-center">Kyndo</h1>
        <p className="text-gray-500 text-center mb-8 text-sm">Acesse o quadro de tarefas</p>
        
        {erro && <div className="bg-red-100 text-red-700 p-3 rounded-lg mb-4 text-sm font-bold text-center">{erro}</div>}
        
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Usuário</label>
            <input type="text" value={nome} onChange={e => setNome(e.target.value)} className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:border-emerald-500" required />
          </div>
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Senha</label>
            <input type="password" value={senha} onChange={e => setSenha(e.target.value)} className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:border-emerald-500" required />
          </div>
          <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl transition-colors shadow-lg mt-4">
            Entrar
          </button>
        </form>
      </div>
    </div>
  );
}

// Change Password Screen
function ChangePasswordScreen({ user, onPasswordChanged }) {
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmarSenha, setConfirmarSenha] = useState('');
  const [erro, setErro] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (novaSenha !== confirmarSenha) {
      setErro('As senhas digitadas não coincidem.'); return;
    }
    if (novaSenha.length < 4) {
      setErro('A senha deve ter pelo menos 4 caracteres.'); return;
    }

    try {
      const res = await authFetch(`${API}/users/${user.id}/password`, {
        method: 'PUT',
        body: JSON.stringify({ nova_senha: novaSenha })
      });

      if (res.ok) {
        onPasswordChanged();
      } else {
        setErro('Erro ao alterar a senha.');
      }
    } catch (err) {
      setErro('Erro de conexão.');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-800 to-teal-900 flex items-center justify-center p-4">
      <div className="bg-white p-8 rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex justify-center mb-4"><KeyRound size={48} className="text-orange-500" /></div>
        <h2 className="text-2xl font-black text-gray-800 text-center mb-2">Quase lá, {user.nome}!</h2>
        <p className="text-gray-500 text-center mb-6 text-sm">Você está usando uma senha temporária. Por favor, crie uma nova senha de segurança para continuar.</p>
        
        {erro && <div className="bg-red-100 text-red-700 p-3 rounded-lg mb-4 text-sm font-bold text-center">{erro}</div>}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Nova Senha</label>
            <input type="password" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:border-orange-500" required />
          </div>
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Confirmar Nova Senha</label>
            <input type="password" value={confirmarSenha} onChange={e => setConfirmarSenha(e.target.value)} className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:border-orange-500" required />
          </div>
          <button type="submit" className="w-full bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 rounded-xl transition-colors shadow-lg mt-4">
            Salvar e Entrar
          </button>
        </form>
      </div>
    </div>
  );
}

// Admin Panel
function AdminPanel({ onBack, currentUsers, refreshUsers }) {
  const [novoNome, setNovoNome] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [novoRole, setNovoRole] = useState('user');
  const [msg, setMsg] = useState('');

  const criarUsuario = async (e) => {
    e.preventDefault();
    const res = await authFetch(`${API}/users`, {
      method: 'POST',
      body: JSON.stringify({ nome: novoNome, senha: novaSenha, role: novoRole })
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
    if(!window.confirm("Certeza que deseja excluir este usuário?")) return;
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
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${u.role === 'superadmin' ? 'bg-purple-100 text-purple-700' : u.role === 'admin' ? 'bg-orange-100 text-orange-700' : 'bg-gray-100 text-gray-600'}`}>{u.role === 'superadmin' ? 'Super Admin' : u.role === 'admin' ? 'Admin' : 'Usuário'}</span>
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

// Board Components
function ListActionsMenu({ col, user, onClose, onAddCard, onArchiveList, onUpdateCol }) {
  const menuRef = useRef();

  useEffect(() => {
    function handleClickOutside(event) { if (menuRef.current && !menuRef.current.contains(event.target)) onClose(); }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  if (user.role !== 'admin' && user.role !== 'superadmin') return null;

  return (
    <div ref={menuRef} className="absolute top-12 right-2 w-64 bg-white rounded-xl shadow-2xl border border-gray-200 z-[100] p-3 space-y-1 animate-in fade-in zoom-in-95">
      <div className="flex justify-between items-center pb-2 mb-2 border-b border-gray-200">
        <h4 className="text-sm font-semibold text-gray-700 text-center flex-grow">Configurações</h4>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 rounded-full p-1 hover:bg-gray-100"><X size={16} /></button>
      </div>

      <button onClick={() => { onUpdateCol({ ...col, publica: !col.publica }); onClose(); }} className="w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-3 text-gray-800 hover:bg-gray-100 transition-colors font-semibold">
        {col.publica ? <Lock size={16} className="text-orange-500"/> : <Unlock size={16} className="text-emerald-500"/>}
        {col.publica ? 'Tornar Privada' : 'Tornar Pública'}
      </button>

      <button onClick={() => { onAddCard(); onClose(); }} className="w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-3 text-gray-800 hover:bg-gray-100 transition-colors">
        <Plus size={16} className="text-gray-500"/> Adicionar cartão
      </button>

      <div className="pt-2 mt-2 border-t border-gray-200">
        <div className="flex items-center gap-2 text-xs text-gray-500 font-bold uppercase tracking-wider mb-1 px-1"><Settings size={14}/> Automações</div>
        <button onClick={() => { onUpdateCol({ ...col, auto_andamento: !col.auto_andamento }); }} className="w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between text-gray-700 hover:bg-gray-100 transition-colors">
          <span>Receber iniciadas {'>0%'}</span>
          {col.auto_andamento ? <CheckCircle2 size={16} className="text-emerald-500"/> : <Circle size={16} className="text-gray-300"/>}
        </button>
        <button onClick={() => { onUpdateCol({ ...col, auto_concluido: !col.auto_concluido }); }} className="w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between text-gray-700 hover:bg-gray-100 transition-colors">
          <span>Receber concluídas 100%</span>
          {col.auto_concluido ? <CheckCircle2 size={16} className="text-green-500"/> : <Circle size={16} className="text-gray-300"/>}
        </button>
      </div>
      
      <button onClick={() => { onArchiveList(); onClose(); }} className="w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-3 text-red-700 hover:bg-red-50 mt-2 transition-colors border-t border-gray-200">
        <Archive size={16} className="text-red-500"/> Arquivar lista
      </button>

      <div className="pt-3 mt-2 border-t border-gray-200 space-y-2">
        <div className="flex items-center gap-2 text-sm text-gray-700 font-medium"><Palette size={16} className="text-gray-500"/> Cor da Lista</div>
        <div className="grid grid-cols-6 gap-2 pt-1">
          {[
            '#ebecf0', '#94a3b8',
            '#fecaca', '#f87171',
            '#fed7aa', '#fb923c',
            '#fef08a', '#fde047',
            '#bbf7d0', '#4ade80',
            '#99f6e4', '#2dd4bf',
            '#bfdbfe', '#60a5fa',
            '#e9d5ff', '#c084fc',
            '#fbcfe8', '#f472b6',
          ].map(color => (
            <button key={color} onClick={() => onUpdateCol({ ...col, cor: color })} className="w-full h-6 rounded border border-black/10 hover:scale-110 transition-transform" style={{ backgroundColor: color }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function CardModal({ card, col, user, allUsers, onClose, onSave, onDelete }) {
  const [titulo, setTitulo] = useState(card?.titulo || '');
  const [desc, setDesc] = useState(card?.descricao || '');
  const [checklist, setChecklist] = useState(card?.checklist || []);
  const [prioridade, setPrioridade] = useState(card?.prioridade || 'Normal');
  const [comentarios, setComentarios] = useState(card?.comentarios || []);
  const [prazo, setPrazo] = useState(card?.prazo || '');
  const [responsaveis, setResponsaveis] = useState(
    card?.responsaveis?.length > 0 ? card.responsaveis : (card?.autor ? [card.autor] : [user.nome])
  );
  const [githubUrl, setGithubUrl] = useState(card?.github_url || '');
  const [novaSubtarefa, setNovaSubtarefa] = useState('');
  const [novoComentario, setNovoComentario] = useState('');
  const [prioridadeAberto, setPrioridadeAberto] = useState(false);
  const [githubMenuAberto, setGithubMenuAberto] = useState(false);
  const [githubUrlTemp, setGithubUrlTemp] = useState('');
  const [editingItemId, setEditingItemId] = useState(null);
  const [editingItemText, setEditingItemText] = useState('');
  const [expandedItemId, setExpandedItemId] = useState(null);
  const [editingSubItemId, setEditingSubItemId] = useState(null);
  const [editingSubItemText, setEditingSubItemText] = useState('');
  const [novaSubetapa, setNovaSubetapa] = useState('');

  const isAdmin = user.role === 'admin' || user.role === 'superadmin';
  const isSuperAdmin = user.role === 'superadmin';
  const isAuthor = card?.autor === user.nome;
  
  const podeEditarDescricao = isAdmin || (col?.publica && (isAuthor || !card?.id));
  const podeDeletar = card?.id && (isAdmin || (isAuthor && col?.id === 'col-1'));

  const mostrarPrioridade = isAdmin || prioridade !== 'Normal' || col?.id !== 'col-1';
  const mostrarPrazo = isAdmin || prazo;
  const mostrarEtapas = isAdmin || checklist.length > 0;

  const handleDescChange = (e) => { setDesc(e.target.value.replace(/(^|\n)-\s/g, "$1• ")); };
  const handleDescKeyDown = (e) => {
    if (e.key === 'Enter') {
      const pos = e.target.selectionStart;
      const lines = desc.substring(0, pos).split('\n');
      const curLine = lines[lines.length - 1];
      if (curLine === '• ') { e.preventDefault(); setDesc(desc.substring(0, pos - 2) + '\n' + desc.substring(pos)); setTimeout(() => e.target.selectionStart = e.target.selectionEnd = pos - 1, 0); return; }
      if (curLine.startsWith('• ')) { e.preventDefault(); setDesc(desc.substring(0, pos) + '\n• ' + desc.substring(pos)); setTimeout(() => e.target.selectionStart = e.target.selectionEnd = pos + 3, 0); return; }
    }
  };

  const addSubtarefa = () => { if (!novaSubtarefa.trim() || !isAdmin) return; setChecklist([...checklist, { id: `sub-${Date.now()}`, texto: novaSubtarefa, concluido: false, criador: user.nome }]); setNovaSubtarefa(''); };
  const addComentario = () => { if (!novoComentario.trim()) return; const dataAtual = new Date().toLocaleDateString('pt-BR', { hour: '2-digit', minute: '2-digit' }); setComentarios([...comentarios, { id: `msg-${Date.now()}`, autor: user.nome, texto: novoComentario, data: dataAtual }]); setNovoComentario(''); };

  const percentual = checklist.length > 0 ? Math.round(
    checklist.reduce((acc, item) => {
      const subs = item.subetapas || [];
      return acc + (subs.length === 0 ? (item.concluido ? 1 : 0) : subs.filter(s => s.concluido).length / subs.length);
    }, 0) / checklist.length * 100
  ) : 0;

  return (
    <div className="fixed inset-0 bg-black/60 z-[200] flex items-center justify-center p-2 md:p-4 backdrop-blur-sm">
      <div className="bg-white w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[95vh]">
        <div className="p-4 md:p-6 border-b flex justify-between items-start bg-gray-50/50">
          <div className="flex-grow flex flex-col gap-2 min-w-0">
            <div className="flex justify-between items-center w-full pr-4">
              <input disabled={!podeEditarDescricao} value={titulo} onChange={e => setTitulo(e.target.value)} className={`text-xl md:text-2xl font-bold w-full outline-none bg-transparent ${!podeEditarDescricao ? 'text-gray-600' : ''}`} placeholder="Título da demanda..." />
              
              {mostrarPrioridade && (
                <div className="flex items-center gap-1 md:gap-2 shrink-0 ml-2 relative">
                  <Tag size={14} className="text-gray-400 hidden md:block"/>
                  {isAdmin ? (
                    <div className="relative">
                      <div onClick={() => setPrioridadeAberto(!prioridadeAberto)} className={`flex items-center gap-1 text-[10px] md:text-xs font-bold uppercase rounded-lg px-2 py-1 outline-none cursor-pointer transition-colors ${PRIORIDADES_BADGE[prioridade]}`}>
                        {prioridade} <ChevronDown size={12} />
                      </div>
                      {prioridadeAberto && (
                        <>
                          <div className="fixed inset-0 z-[210]" onClick={() => setPrioridadeAberto(false)} />
                          <div className="absolute top-full mt-1 right-0 w-32 bg-white rounded-xl shadow-xl border border-gray-200 z-[220] overflow-hidden animate-in fade-in zoom-in-95">
                            {['Baixa', 'Normal', 'Alta', 'Urgente'].map(prio => (
                              <div key={prio} onClick={() => { setPrioridade(prio); setPrioridadeAberto(false); }} className={`p-2 px-3 hover:bg-gray-100 cursor-pointer flex items-center transition-colors ${prioridade === prio ? 'bg-gray-50' : ''}`}>
                                <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded w-full text-center ${PRIORIDADES_BADGE[prio]}`}>{prio}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <span className={`text-[10px] md:text-xs font-bold uppercase rounded-lg px-2 py-1 ${PRIORIDADES_BADGE[prioridade]}`}>{prioridade}</span>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2 md:gap-4 text-[10px] md:text-xs font-bold uppercase tracking-widest mt-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-gray-400 text-[10px] md:text-xs font-bold uppercase tracking-widest">Responsável:</span>
                {responsaveis.map(nome => (
                  <span key={nome} className={`flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded-full ${userColor(nome)}`}>
                    {nome}
                    {isSuperAdmin && responsaveis.length > 1 && (
                      <button onClick={e => { e.stopPropagation(); setResponsaveis(responsaveis.filter(r => r !== nome)); }} className="hover:text-red-600 leading-none">×</button>
                    )}
                  </span>
                ))}
                {isSuperAdmin && (
                  <select value="" onChange={e => { if (e.target.value && !responsaveis.includes(e.target.value)) setResponsaveis([...responsaveis, e.target.value]); }} className="text-[10px] font-bold border border-dashed border-gray-300 rounded-full px-1.5 py-0.5 outline-none bg-transparent text-gray-500 cursor-pointer">
                    <option value="">+ add</option>
                    {(allUsers || []).filter(u => !responsaveis.includes(u.nome)).map(u => <option key={u.id} value={u.nome}>{u.nome}</option>)}
                  </select>
                )}
              </div>
              {card?.data_criacao && <p className="text-gray-400 hidden md:block">Criado em: {card.data_criacao}</p>}
              
              {mostrarPrazo && (
                <div className="flex items-center gap-1 bg-white border border-gray-200 px-2 py-1 rounded text-gray-600">
                  <Calendar size={12} className="text-orange-500" />
                  {isAdmin ? (
                    <input type="date" value={prazo} onChange={e => setPrazo(e.target.value)} className="bg-transparent outline-none cursor-pointer text-gray-800"/>
                  ) : (
                    <span className="font-bold text-gray-800">{formatarData(prazo)}</span>
                  )}
                </div>
              )}

              <div className="relative flex items-center gap-1 shrink-0">
                {githubUrl && (
                  <a href={githubUrl} target="_blank" rel="noopener noreferrer" title="Abrir repositório no GitHub" className="flex items-center justify-center w-8 h-8 bg-white border border-gray-200 rounded-lg text-gray-800 hover:text-black hover:border-gray-400 transition-colors">
                    <GitHubIcon size={20} />
                  </a>
                )}
                <button
                  onClick={() => { setGithubUrlTemp(githubUrl); setGithubMenuAberto(true); }}
                  title="Configurar repositório GitHub"
                  className="flex items-center justify-center w-7 h-7 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                >
                  <MoreHorizontal size={16} />
                </button>
                {githubMenuAberto && (
                  <>
                    <div className="fixed inset-0 z-[210]" onClick={() => setGithubMenuAberto(false)} />
                    <div className="absolute top-full mt-1 right-0 w-64 bg-white rounded-xl shadow-xl border border-gray-200 z-[220] p-3 animate-in fade-in zoom-in-95">
                      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-2">Repositório GitHub</p>
                      <div className="flex gap-1.5">
                        <input
                          autoFocus
                          type="text"
                          value={githubUrlTemp}
                          onChange={e => setGithubUrlTemp(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') { setGithubUrl(githubUrlTemp); setGithubMenuAberto(false); } if (e.key === 'Escape') setGithubMenuAberto(false); }}
                          placeholder="https://github.com/..."
                          className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"
                        />
                        <button
                          onClick={() => { setGithubUrl(githubUrlTemp); setGithubMenuAberto(false); }}
                          className="px-2 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors"
                        >OK</button>
                      </div>
                      {githubUrl && (
                        <button
                          onClick={() => { setGithubUrl(''); setGithubUrlTemp(''); setGithubMenuAberto(false); }}
                          className="mt-2 text-[10px] text-red-400 hover:text-red-600 font-bold"
                        >Remover repositório</button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 shrink-0 p-1"><X size={24}/></button>
        </div>
        
        <div className="p-4 md:p-8 space-y-6 md:space-y-8 overflow-y-auto custom-scrollbar">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-gray-700 font-bold text-sm"><AlignLeft size={16}/> Descrição</div>
            {podeEditarDescricao ? (
              <textarea value={desc} onChange={handleDescChange} onKeyDown={handleDescKeyDown} className="w-full h-24 md:h-32 p-3 md:p-4 bg-gray-50 rounded-xl border border-gray-200 outline-none focus:bg-white text-sm font-mono shadow-inner resize-none" placeholder="Dica: Use '- ' para criar listas..." />
            ) : (
              <div className="w-full min-h-[6rem] p-3 md:p-4 bg-gray-50 rounded-xl border border-gray-200 text-sm font-mono shadow-inner whitespace-pre-wrap break-words">
                {desc ? renderTextWithLinks(desc) : <span className="text-gray-400">Apenas visualização.</span>}
              </div>
            )}
          </div>

          {mostrarEtapas && (
            <>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-gray-700 font-bold text-sm"><CheckSquare size={16}/> Etapas</div>
                  {checklist.length > 0 && <span className="text-sm font-bold text-gray-500">{percentual}%</span>}
                </div>
                {checklist.length > 0 && (<div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden"><div className={`h-full transition-all duration-300 ${percentual === 100 ? 'bg-emerald-500' : 'bg-teal-500'}`} style={{ width: `${percentual}%` }} /></div>)}
                <div className="space-y-1">
                  {checklist.map(item => {
                    const subetapas = item.subetapas || [];
                    const isExpanded = expandedItemId === item.id;
                    return (
                      <div key={item.id} className="mb-1">
                        {/* Linha principal da etapa */}
                        <div className="flex items-center gap-2 group/item">
                          <button
                            disabled={!isAdmin}
                            onClick={() => {
                              const nowDone = !item.concluido;
                              setChecklist(checklist.map(i => i.id === item.id ? {
                                ...i,
                                concluido: nowDone,
                                concluidoPor: nowDone ? user.nome : null,
                                subetapas: nowDone ? (i.subetapas||[]).map(s => ({...s, concluido: true, concluidoPor: user.nome})) : (i.subetapas||[])
                              } : i));
                            }}
                            className={`${!isAdmin ? 'cursor-default' : 'cursor-pointer hover:scale-110 transition-transform'} shrink-0`}
                          >
                            {item.concluido ? <CheckCircle2 size={16} className="text-emerald-500"/> : <Circle size={16} className="text-gray-300"/>}
                          </button>
                          {isAdmin && editingItemId === item.id ? (
                            <input value={editingItemText} onChange={e => setEditingItemText(e.target.value)} onBlur={() => { if (editingItemText.trim()) setChecklist(checklist.map(i => i.id === item.id ? {...i, texto: editingItemText.trim()} : i)); setEditingItemId(null); }} onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') setEditingItemId(null); }} className="flex-1 min-w-0 text-sm border-b-2 border-emerald-400 outline-none bg-transparent text-gray-700 py-0.5" autoFocus />
                          ) : (
                            <span className={`flex-1 min-w-0 text-sm ${item.concluido ? 'text-gray-400 line-through' : 'text-gray-700'} ${isAdmin ? 'cursor-pointer hover:text-emerald-600' : ''}`} onClick={() => { if (isAdmin) { setEditingItemId(item.id); setEditingItemText(item.texto); } }}>{item.texto}</span>
                          )}
                          <div className="flex items-center gap-1 shrink-0">
                            {item.concluido && item.concluidoPor && item.concluidoPor === item.criador
                              ? <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(item.concluidoPor)}`}>✓ {item.concluidoPor}</span>
                              : <>{item.criador && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ${userColor(item.criador)}`}>{item.criador}</span>}
                              {item.concluido && item.concluidoPor && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(item.concluidoPor)}`}>✓ {item.concluidoPor}</span>}</>}
                            {isAdmin && <button onClick={() => setChecklist(checklist.filter(i => i.id !== item.id))} className="opacity-0 group-hover/item:opacity-100 p-0.5 text-red-400 hover:text-red-600 transition-all"><X size={14}/></button>}
                            <button onClick={() => { setExpandedItemId(isExpanded ? null : item.id); setNovaSubetapa(''); }} className="p-0.5 text-gray-400 hover:text-emerald-500 transition-colors" title="Descrição / observações">
                              {isExpanded ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}
                            </button>
                          </div>
                        </div>

                        {/* Descrição — só aparece quando expandido */}
                        {isExpanded && (
                          <div className="ml-7 mt-1 mb-2 pl-3 border-l-2 border-emerald-300 space-y-2">
                            <textarea
                              value={item.notas || ''}
                              onChange={e => setChecklist(checklist.map(i => i.id === item.id ? {...i, notas: e.target.value} : i))}
                              disabled={!isAdmin}
                              placeholder={isAdmin ? 'Observações, anotações ou descrição desta etapa...' : 'Sem observações.'}
                              className="w-full h-20 p-2 bg-gray-50 rounded-lg border border-gray-200 outline-none focus:bg-white text-sm resize-none"
                            />
                            {isAdmin && (
                              <div className="flex gap-2">
                                <input value={novaSubetapa} onChange={e => setNovaSubetapa(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && novaSubetapa.trim()) { setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: [...(i.subetapas||[]), {id:`sub-${Date.now()}`, texto: novaSubetapa.trim(), concluido: false, criador: user.nome}]} : i)); setNovaSubetapa(''); } }} className="flex-1 p-1.5 border rounded text-xs outline-none focus:border-emerald-400" placeholder="Adicionar sub-etapa..." />
                                <button onClick={() => { if (!novaSubetapa.trim()) return; setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: [...(i.subetapas||[]), {id:`sub-${Date.now()}`, texto: novaSubetapa.trim(), concluido: false, criador: user.nome}]} : i)); setNovaSubetapa(''); }} className="px-3 py-1.5 bg-emerald-600 text-white rounded text-xs font-bold">Add</button>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Sub-etapas — sempre visíveis, indentadas */}
                        {subetapas.length > 0 && (
                          <div className="ml-7 pl-3 mt-1 border-l-2 border-gray-200 space-y-1">
                            {subetapas.map(sub => (
                              <div key={sub.id} className="flex items-center gap-2 group/sub">
                                <button onClick={() => setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: (i.subetapas||[]).map(s => s.id === sub.id ? {...s, concluido: !s.concluido, concluidoPor: !s.concluido ? user.nome : null} : s)} : i))} className="shrink-0 cursor-pointer hover:scale-110 transition-transform">
                                  {sub.concluido ? <CheckCircle2 size={16} className="text-emerald-500"/> : <Circle size={16} className="text-gray-300"/>}
                                </button>
                                {isAdmin && editingSubItemId === sub.id ? (
                                  <input value={editingSubItemText} onChange={e => setEditingSubItemText(e.target.value)} onBlur={() => { if (editingSubItemText.trim()) setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: (i.subetapas||[]).map(s => s.id === sub.id ? {...s, texto: editingSubItemText.trim()} : s)} : i)); setEditingSubItemId(null); }} onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') setEditingSubItemId(null); }} className="flex-1 min-w-0 text-sm border-b border-emerald-400 outline-none bg-transparent py-0.5" autoFocus />
                                ) : (
                                  <span className={`flex-1 min-w-0 text-sm ${sub.concluido ? 'text-gray-400 line-through' : 'text-gray-600'} ${isAdmin ? 'cursor-pointer hover:text-emerald-600' : ''}`} onClick={() => { if (isAdmin) { setEditingSubItemId(sub.id); setEditingSubItemText(sub.texto); } }}>{sub.texto}</span>
                                )}
                                <div className="flex items-center gap-1 shrink-0">
                                  {sub.concluido && sub.concluidoPor && sub.concluidoPor === sub.criador
                                    ? <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(sub.concluidoPor)}`}>✓ {sub.concluidoPor}</span>
                                    : <>{sub.criador && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ${userColor(sub.criador)}`}>{sub.criador}</span>}
                                    {sub.concluido && sub.concluidoPor && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full whitespace-nowrap ring-1 ring-emerald-400 ${userColor(sub.concluidoPor)}`}>✓ {sub.concluidoPor}</span>}</>}
                                  {isAdmin && <button onClick={() => setChecklist(checklist.map(i => i.id === item.id ? {...i, subetapas: (i.subetapas||[]).filter(s => s.id !== sub.id)} : i))} className="opacity-0 group-hover/sub:opacity-100 p-0.5 text-red-400 hover:text-red-600 transition-all"><X size={14}/></button>}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                {isAdmin && (
                  <div className="flex flex-row items-center gap-2 pt-2 w-full">
                    <input value={novaSubtarefa} onChange={e => setNovaSubtarefa(e.target.value)} onKeyDown={e => e.key === 'Enter' && addSubtarefa()} className="flex-grow min-w-0 p-2 border rounded-lg text-sm outline-none focus:border-emerald-400" placeholder="Adicionar etapa..." />
                    <button onClick={addSubtarefa} className="shrink-0 px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-bold shadow-md">Add</button>
                  </div>
                )}
              </div>
              <hr className="border-gray-200" />
            </>
          )}

          <div className="space-y-4">
            <div className="flex items-center gap-2 text-gray-700 font-bold text-sm"><MessageSquare size={16}/> Comentários</div>
            <div className="space-y-3">
              {comentarios.map(msg => {
                const autorNoBanco = allUsers.find(u => u.nome === msg.autor);
                const isAdminComment = autorNoBanco?.role === 'admin' || autorNoBanco?.role === 'superadmin';
                const isAuthorComment = msg.autor === (card?.autor || user.nome);
                let boxClass = "bg-gray-50 border-gray-100"; let badge = null;
                if (isAdminComment) { boxClass = "bg-orange-50 border-orange-100"; badge = <span className="ml-2 text-[9px] bg-orange-200 text-orange-800 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Admin</span>; } 
                else if (isAuthorComment) { boxClass = "bg-emerald-50 border-emerald-100"; badge = <span className="ml-2 text-[9px] bg-emerald-200 text-emerald-800 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Solicitante</span>; }
                return (
                  <div key={msg.id} className={`p-3 rounded-xl border ${boxClass}`}>
                    <div className="flex justify-between items-center mb-1">
                      <div className="flex items-center"><span className="text-xs font-bold text-gray-800">{msg.autor}</span>{badge}</div>
                      <span className="text-[10px] text-gray-400 font-semibold">{msg.data}</span>
                    </div>
                    <p className="text-sm text-gray-700">{msg.texto}</p>
                  </div>
                );
              })}
            </div>
            <div className="flex flex-row gap-2 items-center mt-2 w-full">
              <textarea value={novoComentario} onChange={e => setNovoComentario(e.target.value)} className="flex-grow min-w-0 p-3 bg-gray-50 border border-gray-200 rounded-xl text-sm outline-none focus:border-emerald-400 resize-none h-16 md:h-20" placeholder="Escreva um comentário..."/>
              <button onClick={addComentario} className="shrink-0 w-16 h-16 md:w-20 md:h-20 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-colors flex items-center justify-center"><Send size={18} className="ml-1" /></button>
            </div>
          </div>
        </div>
        <div className="p-3 md:p-4 bg-gray-100 flex justify-end gap-2 md:gap-3 border-t">
          {podeDeletar && <button onClick={() => onDelete(card.id)} className="text-red-600 px-2 py-2 md:px-4 font-bold text-[10px] md:text-sm mr-auto hover:bg-red-50 rounded-lg transition-colors">Excluir</button>}
          <button onClick={onClose} className="px-3 md:px-5 py-2 font-bold text-xs md:text-sm hover:bg-gray-200 rounded-lg transition-colors">Fechar</button>
          <button onClick={() => onSave({...card, titulo, descricao: desc, checklist, prioridade, comentarios, prazo, autor: card?.autor || user.nome, responsaveis, github_url: githubUrl})} className="px-4 md:px-6 py-2 bg-emerald-600 text-white rounded-lg font-bold text-xs md:text-sm shadow-lg hover:bg-emerald-700 transition-colors">Salvar Tudo</button>
        </div>
      </div>
    </div>
  );
}

// Notas View
// ── Obsidian-style notes ────────────────────────────────────────────────────

const NODE_COLORS = {
  blue:    { bg: '#dbeafe', border: '#2563eb', text: '#1e3a8a' },
  emerald: { bg: '#d1fae5', border: '#059669', text: '#064e3b' },
  purple:  { bg: '#ede9fe', border: '#7c3aed', text: '#4c1d95' },
  orange:  { bg: '#ffedd5', border: '#ea580c', text: '#7c2d12' },
  pink:    { bg: '#fce7f3', border: '#db2777', text: '#831843' },
  yellow:  { bg: '#fef9c3', border: '#ca8a04', text: '#713f12' },
};

function TextEditor({ noteId, conteudo, allNotes, onChange, onOpenNote }) {
  const [local, setLocal] = useState(conteudo);
  const timer = useRef(null);

  useEffect(() => { setLocal(conteudo); }, [noteId]);

  const handle = (e) => {
    const v = e.target.value;
    setLocal(v);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange(v), 700);
  };

  // Detect [[links]] in real-time, deduplicated
  const uniqueLinks = [...new Map(
    [...local.matchAll(/\[\[([^\]]+)\]\]/g)].map(m => {
      const name = m[1].trim();
      const linked = allNotes.find(n => n.titulo?.trim().toLowerCase() === name.toLowerCase());
      return [name.toLowerCase(), { name, linked }];
    })
  ).values()];

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <textarea value={local} onChange={handle}
        className="flex-1 bg-transparent text-white/90 placeholder-white/20 p-6 text-sm leading-relaxed outline-none resize-none font-mono custom-scrollbar"
        placeholder={"Escreva suas anotações...\n\nUse [[Nome da Nota]] para linkar outras notas."}
        style={{ caretColor: '#34d399' }}
      />
      {uniqueLinks.length > 0 && (
        <div className="shrink-0 flex items-center gap-2 px-4 py-2 border-t border-white/8 bg-black/15 flex-wrap">
          <span className="text-white/25 text-[10px] font-mono shrink-0">Links:</span>
          {uniqueLinks.map(({ name, linked }) => (
            <button key={name} onClick={() => linked && onOpenNote(linked.id)}
              disabled={!linked}
              className={`text-[11px] font-bold px-2.5 py-0.5 rounded-lg transition-colors ${linked ? 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 cursor-pointer' : 'bg-white/8 text-white/22 cursor-default line-through'}`}
              title={linked ? `Abrir nota: ${linked.titulo}` : 'Nota não encontrada'}>
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function CanvasEditor({ noteId, data, allNotes, onChange, onOpenNote }) {
  const [nodes, setNodes]           = useState(() => data?.nodes || []);
  const [edges, setEdges]           = useState(() => data?.edges || []);
  const [pan, setPan]               = useState({ x: 100, y: 60 });
  const [zoom, setZoom]             = useState(1);
  const [selected, setSelected]     = useState(null);
  const [connecting, setConnecting] = useState(null);
  const [editingId, setEditingId]   = useState(null);
  const [linkVal, setLinkVal]       = useState('');

  const containerRef  = useRef(null);
  const nodesRef      = useRef(nodes);
  const edgesRef      = useRef(edges);
  const saveTimer     = useRef(null);
  const panStart      = useRef(null);
  const panning       = useRef(false);
  const editTextRef   = useRef(''); // source of truth during contenteditable editing

  useEffect(() => { nodesRef.current = nodes; }, [nodes]);
  useEffect(() => { edgesRef.current = edges; }, [edges]);

  useEffect(() => {
    const ns = data?.nodes || [], es = data?.edges || [];
    setNodes(ns); nodesRef.current = ns;
    setEdges(es); edgesRef.current = es;
    setSelected(null); setConnecting(null); setEditingId(null);
    setPan({ x: 100, y: 60 }); setZoom(1);
  }, [noteId]);

  const doSave = () => {
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => onChange({ nodes: nodesRef.current, edges: edgesRef.current }), 600);
  };

  const genId = () => `${Date.now()}${Math.random().toString(36).slice(2, 5)}`;

  const toCanvas = (sx, sy) => {
    const r = containerRef.current.getBoundingClientRect();
    return { x: (sx - r.left - pan.x) / zoom, y: (sy - r.top - pan.y) / zoom };
  };

  const finishEdit = (id) => {
    const target = id ?? editingId;
    if (!target) return;
    const txt = editTextRef.current;
    setNodes(prev => { const nxt = prev.map(n => n.id === target ? { ...n, text: txt } : n); nodesRef.current = nxt; doSave(); return nxt; });
    setEditingId(null);
    editTextRef.current = '';
  };

  const startEdit = (node) => {
    editTextRef.current = node.text || '';
    setEditingId(node.id);
  };

  // Contenteditable ref: initialize content + focus once on mount
  const editDivRef = (el) => {
    if (!el || el.hasAttribute('data-ce-init')) return;
    el.setAttribute('data-ce-init', '1');
    el.textContent = editTextRef.current;
    el.focus();
    try {
      const r = document.createRange();
      r.selectNodeContents(el);
      r.collapse(false);
      window.getSelection()?.removeAllRanges();
      window.getSelection()?.addRange(r);
    } catch (_) {}
  };

  // Background handlers
  const onBgDown = (e) => {
    if (e.button !== 0) return;
    if (editingId) { finishEdit(editingId); return; }
    setSelected(null);
    if (connecting) { setConnecting(null); return; }
    panning.current = true;
    panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };
  const onBgMove  = (e) => { if (panning.current) setPan({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y }); };
  const onBgUp    = ()  => { panning.current = false; };
  const onWheel   = (e) => { e.preventDefault(); setZoom(z => Math.max(0.15, Math.min(4, z * (e.deltaY < 0 ? 1.12 : 0.9)))); };
  const onBgDbl   = (e) => {
    const pos = toCanvas(e.clientX, e.clientY);
    const id = genId();
    const n = { id, x: pos.x - 55, y: pos.y - 22, text: '', color: 'blue' };
    const nxt = [...nodesRef.current, n]; setNodes(nxt); nodesRef.current = nxt; doSave();
    startEdit(n);
  };

  // Node handlers
  const onNodeDown = (e, node) => {
    e.stopPropagation();
    if (editingId && editingId !== node.id) { finishEdit(editingId); return; }
    if (editingId === node.id) return;

    if (connecting) {
      if (connecting !== node.id && !edgesRef.current.find(ed => ed.from === connecting && ed.to === node.id)) {
        const ne = { id: genId(), from: connecting, to: node.id };
        const nxt = [...edgesRef.current, ne]; setEdges(nxt); edgesRef.current = nxt; doSave();
      }
      setConnecting(null); return;
    }

    setSelected({ type: 'node', id: node.id });
    const sx = e.clientX, sy = e.clientY, ox = node.x, oy = node.y;
    let moved = false;
    const mv = (ev) => {
      const dx = (ev.clientX - sx) / zoom, dy = (ev.clientY - sy) / zoom;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) moved = true;
      if (moved) setNodes(prev => { const nxt = prev.map(n => n.id === node.id ? { ...n, x: ox + dx, y: oy + dy } : n); nodesRef.current = nxt; return nxt; });
    };
    const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); if (moved) doSave(); };
    document.addEventListener('mousemove', mv);
    document.addEventListener('mouseup', up);
  };

  const onNodeDbl = (e, node) => {
    e.stopPropagation();
    if (node.linkedNoteId) { onOpenNote(node.linkedNoteId); return; }
    startEdit(node);
  };

  // Resize handle drag
  const startResize = (e, node) => {
    e.stopPropagation();
    const startX = e.clientX, startW = node.w || 120;
    const mv = (ev) => {
      const newW = Math.max(80, Math.min(420, startW + (ev.clientX - startX) / zoom));
      setNodes(prev => { const nxt = prev.map(n => n.id === node.id ? { ...n, w: Math.round(newW) } : n); nodesRef.current = nxt; return nxt; });
    };
    const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); doSave(); };
    document.addEventListener('mousemove', mv);
    document.addEventListener('mouseup', up);
  };

  // Keyboard
  useEffect(() => {
    const kd = (e) => {
      if (editingId) { if (e.key === 'Escape') finishEdit(editingId); return; }
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
      if (e.key === 'Escape') { setConnecting(null); return; }
      if ((e.key === 'Delete' || e.key === 'Backspace') && selected) {
        if (selected.type === 'node') {
          const nn = nodesRef.current.filter(n => n.id !== selected.id);
          const ee = edgesRef.current.filter(ed => ed.from !== selected.id && ed.to !== selected.id);
          setNodes(nn); nodesRef.current = nn; setEdges(ee); edgesRef.current = ee;
        } else {
          const ee = edgesRef.current.filter(ed => ed.id !== selected.id);
          setEdges(ee); edgesRef.current = ee;
        }
        doSave(); setSelected(null);
      }
    };
    window.addEventListener('keydown', kd);
    return () => window.removeEventListener('keydown', kd);
  }, [editingId, selected]);

  const changeColor = (color) => {
    if (!selected || selected.type !== 'node') return;
    const nxt = nodesRef.current.map(n => n.id === selected.id ? { ...n, color } : n);
    setNodes(nxt); nodesRef.current = nxt; doSave();
  };

  const addNode = () => {
    const id = genId();
    const n = { id, x: 180 + nodesRef.current.length * 18, y: 120 + nodesRef.current.length * 18, text: '', color: 'blue' };
    const nxt = [...nodesRef.current, n]; setNodes(nxt); nodesRef.current = nxt; doSave();
    startEdit(n);
  };

  const addNoteLink = (note) => {
    if (!note) return;
    const id = genId();
    const n = { id, x: 200 + nodesRef.current.length * 18, y: 160 + nodesRef.current.length * 18, text: note.titulo, color: 'blue', w: 160, linkedNoteId: note.id };
    const nxt = [...nodesRef.current, n]; setNodes(nxt); nodesRef.current = nxt; doSave();
  };

  const deleteSelected = () => {
    if (!selected) return;
    if (selected.type === 'node') {
      const nn = nodesRef.current.filter(n => n.id !== selected.id);
      const ee = edgesRef.current.filter(ed => ed.from !== selected.id && ed.to !== selected.id);
      setNodes(nn); nodesRef.current = nn; setEdges(ee); edgesRef.current = ee;
    } else {
      const ee = edgesRef.current.filter(ed => ed.id !== selected.id);
      setEdges(ee); edgesRef.current = ee;
    }
    doSave(); setSelected(null);
  };

  const getPath = (fromId, toId) => {
    const f = nodes.find(n => n.id === fromId), t = nodes.find(n => n.id === toId);
    if (!f || !t) return null;
    const fw = f.w || 120, tw = t.w || 120;
    const fx = f.x + fw / 2, fy = f.y + 24;
    const tx = t.x + tw / 2, ty = t.y + 24;
    const dx = tx - fx;
    return `M ${fx} ${fy} C ${fx + dx * 0.5} ${fy}, ${tx - dx * 0.5} ${ty}, ${tx} ${ty}`;
  };

  const selNode = selected?.type === 'node' ? nodes.find(n => n.id === selected.id) : null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="shrink-0 flex items-center gap-1.5 px-3 py-2 border-b border-white/5 bg-black/10 flex-wrap">
        <button onClick={addNode} className="text-xs font-bold px-2.5 py-1 rounded-lg bg-white/10 text-white hover:bg-white/20 transition-colors">+ Balão</button>
        {allNotes.length > 0 && (
          <select value={linkVal} onChange={e => { const n = allNotes.find(x => x.id === e.target.value); addNoteLink(n); setLinkVal(''); }}
            className="text-xs font-bold px-2 py-1 rounded-lg bg-white/10 text-white outline-none cursor-pointer">
            <option value="">+ Link de Nota</option>
            {allNotes.map(n => <option key={n.id} value={n.id}>{n.titulo || 'Sem título'}</option>)}
          </select>
        )}
        {selNode && (<>
          <div className="w-px h-4 bg-white/10 mx-0.5" />
          {Object.entries(NODE_COLORS).map(([k, c]) => (
            <button key={k} onClick={() => changeColor(k)}
              style={{ backgroundColor: c.bg, border: `2px solid ${c.border}` }}
              className={`w-5 h-5 rounded-full transition-transform ${selNode.color === k ? 'scale-125 shadow-md' : 'hover:scale-110'}`} />
          ))}
          <div className="w-px h-4 bg-white/10 mx-0.5" />
          <button onClick={deleteSelected} className="text-xs font-bold px-2.5 py-1 rounded-lg bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors">✕ Deletar</button>
        </>)}
        {selected?.type === 'edge' && (
          <button onClick={deleteSelected} className="text-xs font-bold px-2.5 py-1 rounded-lg bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors">✕ Deletar ligação</button>
        )}
        {connecting && <span className="text-emerald-300 text-[11px] font-bold animate-pulse ml-2">Clique em outro balão para conectar · ESC cancela</span>}
        <span className="text-white/18 text-[10px] font-mono ml-auto hidden md:block">2× clique = balão · scroll = zoom · Del = apagar</span>
      </div>

      {/* Canvas */}
      <div ref={containerRef}
        className="flex-1 relative overflow-hidden select-none"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.09) 1.5px, transparent 1.5px)',
          backgroundSize: `${24 * zoom}px ${24 * zoom}px`,
          backgroundPosition: `${pan.x}px ${pan.y}px`,
          backgroundColor: 'rgba(0,0,0,0.15)',
          cursor: connecting ? 'crosshair' : 'default',
        }}
        onMouseDown={onBgDown}
        onMouseMove={onBgMove}
        onMouseUp={onBgUp}
        onMouseLeave={onBgUp}
        onWheel={onWheel}
        onDoubleClick={onBgDbl}
      >
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none gap-2">
            <p className="text-white/12 font-black text-2xl">Mapa vazio</p>
            <p className="text-white/10 text-xs">Clique em "+ Balão" ou dê duplo clique na tela</p>
          </div>
        )}

        {/* Pan + zoom container */}
        <div style={{ transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`, transformOrigin: '0 0', position: 'absolute', left: 0, top: 0, width: 4000, height: 4000 }}>

          {/* SVG edges */}
          <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, overflow: 'visible', pointerEvents: 'none' }}>
            <defs>
              <marker id="arrN" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                <path d="M0 0 L8 3 L0 6z" fill="rgba(255,255,255,0.28)" />
              </marker>
              <marker id="arrS" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                <path d="M0 0 L8 3 L0 6z" fill="#60a5fa" />
              </marker>
            </defs>
            {edges.map(edge => {
              const d = getPath(edge.from, edge.to);
              if (!d) return null;
              const isSel = selected?.type === 'edge' && selected.id === edge.id;
              return (
                <g key={edge.id} style={{ pointerEvents: 'all', cursor: 'pointer' }}
                  onMouseDown={e => { e.stopPropagation(); setSelected({ type: 'edge', id: edge.id }); }}>
                  <path d={d} stroke="transparent" strokeWidth="14" fill="none" style={{ pointerEvents: 'stroke' }} />
                  <path d={d} stroke={isSel ? '#60a5fa' : 'rgba(255,255,255,0.27)'} strokeWidth={isSel ? 2.5 : 1.5}
                    fill="none" markerEnd={isSel ? 'url(#arrS)' : 'url(#arrN)'} style={{ pointerEvents: 'none' }} />
                </g>
              );
            })}
          </svg>

          {/* Nodes */}
          {nodes.map(node => {
            const c = NODE_COLORS[node.color] || NODE_COLORS.blue;
            const isSel  = selected?.type === 'node' && selected.id === node.id;
            const isConn = connecting === node.id;
            const isEditing = editingId === node.id;
            const nodeW = node.w;

            return (
              <div key={node.id}
                style={{
                  position: 'absolute', left: node.x, top: node.y,
                  // auto-size to content unless user set a fixed width
                  minWidth: nodeW || 80, maxWidth: nodeW || 300,
                  backgroundColor: c.bg,
                  border: `2px solid ${isSel ? '#60a5fa' : isConn ? '#10b981' : c.border}`,
                  borderRadius: 12, padding: '8px 12px',
                  boxShadow: isSel ? '0 0 0 3px rgba(96,165,250,0.28), 0 4px 14px rgba(0,0,0,0.22)' : '0 2px 8px rgba(0,0,0,0.18)',
                  cursor: connecting ? 'crosshair' : 'grab',
                  minHeight: 40, display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  transition: 'border-color 0.1s, box-shadow 0.1s',
                  boxSizing: 'border-box',
                }}
                onMouseDown={e => onNodeDown(e, node)}
                onDoubleClick={e => onNodeDbl(e, node)}
              >
                {node.linkedNoteId && <span style={{ fontSize: 10, marginBottom: 2, opacity: 0.65 }}>🔗</span>}

                {isEditing ? (
                  <div
                    ref={editDivRef}
                    contentEditable
                    suppressContentEditableWarning
                    onInput={e => { editTextRef.current = e.currentTarget.textContent || ''; }}
                    onBlur={() => finishEdit(node.id)}
                    onKeyDown={e => {
                      e.stopPropagation();
                      if (e.key === 'Escape') { e.preventDefault(); finishEdit(node.id); }
                    }}
                    onClick={e => e.stopPropagation()}
                    style={{
                      minWidth: 40, maxWidth: nodeW ? nodeW - 24 : 276,
                      outline: 'none', fontSize: 13, fontWeight: 700,
                      color: c.text, textAlign: 'center', lineHeight: 1.5,
                      wordBreak: 'break-word', whiteSpace: 'pre-wrap', cursor: 'text',
                    }}
                  />
                ) : (
                  <span style={{
                    fontSize: 13, fontWeight: 700, color: c.text, textAlign: 'center',
                    lineHeight: 1.5, wordBreak: 'break-word', whiteSpace: 'pre-wrap',
                    display: 'block', maxWidth: nodeW ? nodeW - 24 : 276,
                  }}>
                    {node.text || <em style={{ opacity: 0.32, fontSize: 11, fontStyle: 'normal' }}>duplo clique</em>}
                  </span>
                )}

                {/* → connection arrow (visible on selected non-editing node) */}
                {isSel && !isEditing && !connecting && (
                  <div
                    style={{
                      position: 'absolute', right: -20, top: '50%', transform: 'translateY(-50%)',
                      width: 20, height: 20, borderRadius: '50%',
                      background: '#10b981', color: 'white',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', fontSize: 13, fontWeight: 900,
                      boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
                      zIndex: 10,
                    }}
                    onMouseDown={e => { e.stopPropagation(); setConnecting(node.id); }}
                    title="Conectar a outro balão"
                  >→</div>
                )}

                {/* Resize handle (bottom-right corner, visible on selected node) */}
                {isSel && !isEditing && (
                  <div
                    style={{
                      position: 'absolute', right: -5, bottom: -5,
                      width: 11, height: 11, borderRadius: 3,
                      background: '#60a5fa', cursor: 'se-resize',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
                    }}
                    onMouseDown={e => startResize(e, node)}
                    title="Redimensionar"
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function NotasView({ user }) {
  const [notes, setNotes]           = useState([]);
  const [activeId, setActiveId]     = useState(null);
  const [search, setSearch]         = useState('');
  const [loading, setLoading]       = useState(true);
  const [saveStatus, setSaveStatus] = useState('idle');
  const saveTimer = useRef(null);

  useEffect(() => {
    authFetch(`${API}/notes`)
      .then(r => r.ok ? r.json() : [])
      .then(data => { setNotes(data); if (data.length > 0) setActiveId(data[0].id); setLoading(false); });
  }, []);

  const activeNote = notes.find(n => n.id === activeId) || null;

  const createNote = (tipo) => {
    authFetch(`${API}/notes`, {
      method: 'POST',
      body: JSON.stringify({ titulo: 'Nova nota', tipo, conteudo: '', canvas_data: tipo === 'canvas' ? { nodes: [], edges: [] } : null }),
    }).then(r => r.ok ? r.json() : null).then(note => {
      if (!note) return;
      setNotes(prev => [note, ...prev]);
      setActiveId(note.id);
    });
  };

  const updateNote = (changes) => {
    if (!activeId || !activeNote) return;
    const updated = { ...activeNote, ...changes };
    setNotes(prev => prev.map(n => n.id === activeId ? updated : n));
    setSaveStatus('saving');
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      authFetch(`${API}/notes/${activeId}`, { method: 'PUT', body: JSON.stringify(updated) })
        .then(() => { setSaveStatus('saved'); setTimeout(() => setSaveStatus('idle'), 2000); });
    }, 700);
  };

  const deleteNote = (noteId, e) => {
    e.stopPropagation();
    const remaining = notes.filter(n => n.id !== noteId);
    setNotes(remaining);
    if (activeId === noteId) setActiveId(remaining[0]?.id || null);
    authFetch(`${API}/notes/${noteId}`, { method: 'DELETE' });
  };

  const filtered = notes.filter(n =>
    n.titulo?.toLowerCase().includes(search.toLowerCase()) ||
    n.conteudo?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="absolute inset-0 flex overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 flex flex-col bg-black/40 backdrop-blur-sm border-r border-white/10">
        <div className="p-3 border-b border-white/10 shrink-0">
          <p className="text-white/50 font-black text-[10px] uppercase tracking-widest mb-2">Notas · {user.nome}</p>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Buscar..." autoComplete="off"
            className="w-full bg-white/10 hover:bg-white/15 text-white placeholder-white/25 text-xs px-3 py-1.5 rounded-lg outline-none focus:bg-white/20 transition-colors" />
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar py-1 min-h-0">
          {loading ? (
            <p className="text-white/20 text-xs text-center py-6">Carregando...</p>
          ) : filtered.length === 0 ? (
            <p className="text-white/15 text-xs text-center py-6 font-bold">{search ? 'Nenhum resultado' : 'Nenhuma nota'}</p>
          ) : filtered.map(note => (
            <div key={note.id} onClick={() => setActiveId(note.id)}
              className={`px-3 py-2.5 cursor-pointer group flex items-start justify-between gap-1 transition-colors ${activeId === note.id ? 'bg-white/15' : 'hover:bg-white/8'}`}>
              <div className="min-w-0 flex-1">
                <p className={`text-xs font-bold truncate ${activeId === note.id ? 'text-white' : 'text-white/60'}`}>{note.titulo || 'Sem título'}</p>
                <p className="text-[10px] text-white/22 mt-0.5">{note.tipo === 'canvas' ? '🗺 Mapa' : '📝 Texto'} · {note.criado_em}</p>
              </div>
              <button onClick={e => deleteNote(note.id, e)}
                className="opacity-0 group-hover:opacity-100 text-white/25 hover:text-red-400 transition-all shrink-0 p-0.5 mt-0.5">
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
        <div className="p-3 border-t border-white/10 shrink-0 flex gap-2">
          <button onClick={() => createNote('texto')}  className="flex-1 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-bold rounded-lg transition-colors">+ Texto</button>
          <button onClick={() => createNote('canvas')} className="flex-1 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-bold rounded-lg transition-colors">+ Mapa</button>
        </div>
      </aside>

      {/* Editor area */}
      {activeNote ? (
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-b border-white/10 bg-black/20">
            <input value={activeNote.titulo || ''} onChange={e => updateNote({ titulo: e.target.value })}
              className="flex-1 bg-transparent text-white font-black text-lg outline-none placeholder-white/25 min-w-0"
              placeholder="Sem título" />
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full transition-all shrink-0 ${saveStatus === 'saving' ? 'bg-yellow-400/20 text-yellow-300' : saveStatus === 'saved' ? 'bg-emerald-400/20 text-emerald-300' : 'opacity-0'}`}>
              {saveStatus === 'saving' ? 'Salvando...' : 'Salvo ✓'}
            </span>
          </div>
          {activeNote.tipo === 'canvas' ? (
            <CanvasEditor key={activeNote.id} noteId={activeNote.id}
              data={activeNote.canvas_data || { nodes: [], edges: [] }}
              allNotes={notes} onChange={canvas_data => updateNote({ canvas_data })} onOpenNote={setActiveId} />
          ) : (
            <TextEditor key={activeNote.id} noteId={activeNote.id}
              conteudo={activeNote.conteudo || ''} allNotes={notes}
              onChange={conteudo => updateNote({ conteudo })} onOpenNote={setActiveId} />
          )}
        </div>
      ) : !loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-white/18 font-black text-xl mb-4">Nenhuma nota ainda</p>
            <div className="flex gap-3 justify-center">
              <button onClick={() => createNote('texto')}  className="px-5 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-bold rounded-xl transition-colors">+ Nota de texto</button>
              <button onClick={() => createNote('canvas')} className="px-5 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-bold rounded-xl transition-colors">+ Mapa mental</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Cronograma View
function CronogramaView({ cards, allUsers, setModal }) {
  const [offsetDays, setOffsetDays] = useState(0);
  const [windowDays, setWindowDays] = useState(28);

  const parseISO = (str) => { if (!str) return null; const [y, m, d] = str.split('-').map(Number); return new Date(y, m - 1, d); };
  const parseBR  = (str) => { if (!str) return null; const [d, m, y] = str.split('/').map(Number); return new Date(y, m - 1, d); };

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const windowStart = new Date(today); windowStart.setDate(windowStart.getDate() + offsetDays);
  const windowEnd   = new Date(windowStart); windowEnd.setDate(windowEnd.getDate() + windowDays);
  const totalRange  = windowEnd - windowStart;
  const todayPct    = Math.max(0, Math.min(100, ((today - windowStart) / totalRange) * 100));

  const days = Array.from({ length: windowDays }, (_, i) => { const d = new Date(windowStart); d.setDate(d.getDate() + i); return d; });

  const BAR_COLORS = {
    'Urgente': { bar: '#ef4444', progress: '#991b1b', text: '#fff' },
    'Alta':    { bar: '#f97316', progress: '#9a3412', text: '#fff' },
    'Normal':  { bar: '#fbbf24', progress: '#b45309', text: '#1f2937' },
    'Baixa':   { bar: '#34d399', progress: '#065f46', text: '#fff' },
  };

  const calcProgress = (card) => {
    const cl = card.checklist || [];
    if (!cl.length) return 0;
    return Math.round(cl.reduce((acc, item) => {
      const subs = item.subetapas || [];
      return acc + (subs.length === 0 ? (item.concluido ? 1 : 0) : subs.filter(s => s.concluido).length / subs.length);
    }, 0) / cl.length * 100);
  };

  const allCards = Object.values(cards);
  const cardsByUser = {};
  (allUsers || []).forEach(u => { cardsByUser[u.nome] = []; });
  allCards.forEach(card => {
    if (!card.prazo) return;
    const resp = card.responsaveis?.length > 0 ? card.responsaveis : [card.autor];
    resp.forEach(nome => {
      if (!cardsByUser[nome]) cardsByUser[nome] = [];
      if (!cardsByUser[nome].find(c => c.id === card.id)) cardsByUser[nome].push(card);
    });
  });
  Object.keys(cardsByUser).forEach(nome => { cardsByUser[nome].sort((a, b) => (a.prazo || '') < (b.prazo || '') ? -1 : 1); });

  const semPrazo = allCards.filter(c => !c.prazo);
  const usersWithCards = Object.entries(cardsByUser).filter(([, uc]) => uc.length > 0);
  const DAY_SHORT  = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S'];
  const MONTHS_BR  = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

  const renderBar = (card, rowIndex) => {
    const start = parseBR(card.data_criacao) || today;
    const end   = parseISO(card.prazo);
    if (!end) return null;
    const clampStart = start < windowStart ? windowStart : start > windowEnd ? windowEnd : start;
    const clampEnd   = end > windowEnd ? windowEnd : end < windowStart ? windowStart : end;
    if (clampStart >= clampEnd) return null;
    const leftPct  = ((clampStart - windowStart) / totalRange) * 100;
    const widthPct = ((clampEnd - clampStart) / totalRange) * 100;
    const pct = calcProgress(card);
    const isPastDue = end < today && pct < 100;
    const isDone    = pct === 100;
    const colors    = BAR_COLORS[card.prioridade || 'Normal'];
    return (
      <div key={card.id} onClick={() => setModal({ card, status: card.status })}
        title={`${card.titulo} — prazo: ${formatarData(card.prazo)}${pct > 0 ? ` — ${pct}% concluído` : ''}`}
        className="absolute rounded-full flex items-center overflow-hidden cursor-pointer hover:brightness-110 transition-all shadow-md"
        style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, 2)}%`, top: `${rowIndex * 44 + 8}px`, height: '30px', backgroundColor: isDone ? '#10b981' : colors.bar, boxShadow: isPastDue ? '0 0 0 2px #dc2626' : undefined, opacity: isDone ? 0.7 : 1 }}>
        {pct > 0 && pct < 100 && <div className="absolute left-0 top-0 h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: colors.progress, opacity: 0.45 }} />}
        <span className="relative z-10 px-3 text-xs font-bold truncate" style={{ color: isDone ? '#fff' : colors.text }}>{card.titulo}</span>
        {pct > 0 && <span className="relative z-10 ml-auto pr-2.5 text-xs font-black shrink-0" style={{ color: isDone ? '#fff' : colors.text, opacity: 0.85 }}>{pct}%</span>}
      </div>
    );
  };

  return (
    <div className="absolute inset-0 flex flex-col overflow-hidden">
      <div className="shrink-0 flex items-center justify-between px-6 py-2 bg-black/30 backdrop-blur-sm border-b border-white/10">
        <div className="flex items-center gap-1.5">
          {[{ label: '2 semanas', days: 14 }, { label: '1 mês', days: 30 }, { label: '3 meses', days: 90 }].map(opt => (
            <button key={opt.days} onClick={() => { setWindowDays(opt.days); setOffsetDays(0); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${windowDays === opt.days ? 'bg-white text-emerald-800' : 'bg-white/15 text-white hover:bg-white/25'}`}>
              {opt.label}
            </button>
          ))}
        </div>
        <div className="absolute left-1/2 -translate-x-1/2 text-white/50 text-xs font-bold uppercase tracking-widest pointer-events-none">
          {windowStart.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })} — {new Date(windowEnd.getTime() - 86400000).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })}
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => setOffsetDays(d => d - windowDays)} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-white/15 text-white hover:bg-white/25 transition-colors flex items-center gap-1"><ChevronLeft size={14}/> Anterior</button>
          <button onClick={() => setOffsetDays(0)} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-white/15 text-white hover:bg-white/25 transition-colors">Hoje</button>
          <button onClick={() => setOffsetDays(d => d + windowDays)} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-white/15 text-white hover:bg-white/25 transition-colors flex items-center gap-1">Próximo <ChevronRight size={14}/></button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar">
        <div className="flex sticky top-0 z-20 bg-emerald-950/95 backdrop-blur-sm shadow-lg">
          <div className="shrink-0 w-44 border-r border-white/10 px-3 py-2 flex items-end">
            <span className="text-[10px] font-black text-white/30 uppercase tracking-widest">Responsável</span>
          </div>
          <div className="flex-1 flex">
            {days.map((day, i) => {
              const isToday   = day.toDateString() === today.toDateString();
              const isWeekend = day.getDay() === 0 || day.getDay() === 6;
              const showMonth = i === 0 || day.getDate() === 1;
              return (
                <div key={i} className={`flex-1 flex flex-col items-center justify-center py-1.5 border-l border-white/5 text-center ${isToday ? 'bg-red-500/20' : isWeekend ? 'bg-white/[0.03]' : ''}`}>
                  {showMonth && <span className="text-[8px] font-black text-white/40 uppercase leading-none">{MONTHS_BR[day.getMonth()]}</span>}
                  <span className={`text-[11px] font-black leading-tight ${isToday ? 'text-red-300' : 'text-white/60'}`}>{day.getDate()}</span>
                  {windowDays <= 30 && <span className={`text-[8px] font-bold leading-none ${isToday ? 'text-red-300/70' : 'text-white/25'}`}>{DAY_SHORT[day.getDay()]}</span>}
                </div>
              );
            })}
          </div>
        </div>
        {usersWithCards.length === 0 ? (
          <div className="flex items-center justify-center h-48 text-white/40 text-sm font-bold">Nenhuma atividade com prazo definido</div>
        ) : usersWithCards.map(([nome, userCards], rowI) => {
          const rowHeight = Math.max(userCards.length * 44 + 16, 64);
          return (
            <div key={nome} className={`flex border-b border-white/[0.08] ${rowI % 2 === 0 ? 'bg-white/[0.04]' : ''}`}>
              <div className="shrink-0 w-44 border-r border-white/10 px-3 flex items-center" style={{ minHeight: `${rowHeight}px` }}>
                <span className={`text-sm font-bold px-2.5 py-1 rounded-full ${userColor(nome)}`}>{nome}</span>
              </div>
              <div className="flex-1 relative" style={{ height: `${rowHeight}px` }}>
                {days.map((day, i) => (day.getDay() === 0 || day.getDay() === 6) && <div key={i} className="absolute top-0 bottom-0 bg-white/[0.03]" style={{ left: `${(i / windowDays) * 100}%`, width: `${(1 / windowDays) * 100}%` }} />)}
                {days.map((_, i) => <div key={i} className="absolute top-0 bottom-0 border-l border-white/[0.05]" style={{ left: `${(i / windowDays) * 100}%` }} />)}
                {todayPct >= 0 && todayPct <= 100 && <div className="absolute top-0 bottom-0 w-0.5 bg-red-400/80 z-10" style={{ left: `${todayPct}%`, boxShadow: '0 0 8px rgba(248,113,113,0.5)' }} />}
                {userCards.map((card, ci) => renderBar(card, ci))}
              </div>
            </div>
          );
        })}
        {semPrazo.length > 0 && (
          <div className="px-6 py-4 border-t border-white/10">
            <p className="text-[10px] font-black text-white/30 uppercase tracking-widest mb-3">Sem prazo definido</p>
            <div className="flex flex-wrap gap-2">
              {semPrazo.map(card => (
                <div key={card.id} onClick={() => setModal({ card, status: card.status })} className="cursor-pointer bg-white/10 hover:bg-white/20 text-white rounded-lg px-3 py-1.5 text-xs font-bold transition-colors border border-white/10">{card.titulo}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Main App
export default function App() {
  const [user, setUser] = useState(null);
  const [allUsers, setAllUsers] = useState([]);
  
  const [currentScreen, setCurrentScreen] = useState('login');
  
  const [filtroAtivo, setFiltroAtivo] = useState('todas');
  const [filtroAberto, setFiltroAberto] = useState(false);
  const [ordenacao, setOrdenacao] = useState('prioridade_desc');
  const [cols, setCols] = useState([]);
  const [cards, setCards] = useState({});
  const [modal, setModal] = useState(null);
  const [activeMenu, setActiveMenu] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [headerVisible, setHeaderVisible] = useState(false);
  const [showLeftArrow, setShowLeftArrow] = useState(false);
  const [showRightArrow, setShowRightArrow] = useState(false);
  const [activeView, setActiveView] = useState('board');
  const boardRef = useRef(null);

  useEffect(() => {
    const el = boardRef.current;
    if (!el) return;
    const handler = (e) => {
      if (e.deltaY !== 0) {
        e.preventDefault();
        el.scrollLeft += e.deltaY;
      }
    };
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, []);

  useEffect(() => {
    const savedUser = localStorage.getItem('demandaflow_user');
    const token = localStorage.getItem('demandaflow_token');
    if (savedUser && token) {
      setUser(JSON.parse(savedUser));
      setCurrentScreen('board');
    } else {
      handleLogout();
    }
  }, []);

  const fetchUsers = async () => {
    const res = await authFetch(`${API}/users`);
    if(res.ok) {
      const data = await res.json();
      setAllUsers(data);
    }
  };

  const sync = async () => {
    if (!user || currentScreen !== 'board') return;
    setIsSyncing(true);
    try {
      const [cRes, kRes, uRes] = await Promise.all([authFetch(`${API}/columns`), authFetch(`${API}/cards`), authFetch(`${API}/users`)]);
      if(cRes.ok && kRes.ok && uRes.ok) {
        const cData = await cRes.json();
        const kData = await kRes.json();
        const uData = await uRes.json();

        setCols(cData);
        setAllUsers(uData);

        const map = {};
        kData.forEach(k => { map[k.id] = k; });
        setCards(map);
      }
    } catch(e) {
      console.error("Erro no sync", e);
    } finally {
      setTimeout(() => setIsSyncing(false), 500);
    }
  };

  useEffect(() => { if(user && currentScreen === 'board') sync(); }, [user, currentScreen]);

  useEffect(() => {
    if (!user || currentScreen !== 'board') return;
    const interval = setInterval(sync, 10000);
    return () => clearInterval(interval);
  }, [user, currentScreen]);

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  };

  const handleLogin = (loggedUser) => {
    localStorage.setItem('demandaflow_token', loggedUser.token);
    if (loggedUser.senha_temporaria) {
      setUser(loggedUser);
      setCurrentScreen('change_password');
    } else {
      setUser(loggedUser);
      localStorage.setItem('demandaflow_user', JSON.stringify(loggedUser));
      setCurrentScreen('board');
    }
  };

  const handlePasswordChanged = () => {
    const updatedUser = { ...user, senha_temporaria: false };
    setUser(updatedUser);
    localStorage.setItem('demandaflow_user', JSON.stringify(updatedUser));
    setCurrentScreen('board');
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('demandaflow_user');
    localStorage.removeItem('demandaflow_token');
    setCurrentScreen('login');
  };

  const handleSaveCard = (d) => {
    let finalStatus = modal.status; let finalPriority = d.prioridade; 
    const cl = d.checklist || [];
    const pct = cl.length > 0 ? Math.round(cl.reduce((acc, item) => {
      const subs = item.subetapas || [];
      return acc + (subs.length === 0 ? (item.concluido ? 1 : 0) : subs.filter(s => s.concluido).length / subs.length);
    }, 0) / cl.length * 100) : 0;
    if (cl.length > 0) {
      if (pct === 100) { const colDestino = cols.find(c => c.auto_concluido); if (colDestino) finalStatus = colDestino.id; } 
      else if (pct > 0) { const colDestino = cols.find(c => c.auto_andamento); const colAtual = cols.find(c => c.id === finalStatus); if (colDestino && !colAtual?.auto_concluido && !colAtual?.auto_andamento) { finalStatus = colDestino.id; } }
    }
    const targetCol = cols.find(c => c.id === finalStatus);
    if (targetCol && targetCol.auto_concluido) { finalPriority = 'Baixa'; }

    const method = d.id ? 'PUT' : 'POST'; const url = d.id ? `${API}/cards/${d.id}` : `${API}/cards`;
    const payload = {...d, status: finalStatus, prioridade: finalPriority};
    authFetch(url, { method, body: JSON.stringify(payload) }).then(res => {
      if (res.ok && method === 'PUT') {
        setCards(prev => prev[d.id] ? {...prev, [d.id]: {...prev[d.id], ...payload}} : prev);
      }
      setModal(null);
      sync();
    });
  };

  const onDragEnd = (result) => {
    const { destination, source, draggableId, type } = result;
    if (!destination || (user.role !== 'admin' && user.role !== 'superadmin')) return;

    if (type === 'column') {
      const newCols = Array.from(cols); const [removed] = newCols.splice(source.index, 1); newCols.splice(destination.index, 0, removed);
      const updated = newCols.map((c, i) => ({ ...c, ordem: i })); setCols(updated);
      updated.forEach(c => authFetch(`${API}/columns/${c.id}`, { method: 'PUT', body: JSON.stringify(c) }));
      return;
    }
    const card = cards[draggableId]; let finalPriority = card.prioridade;
    const targetCol = cols.find(c => c.id === destination.droppableId);
    if (targetCol && targetCol.auto_concluido) { finalPriority = 'Baixa'; }
    authFetch(`${API}/cards/${draggableId}`, { method: 'PUT', body: JSON.stringify({ ...card, status: destination.droppableId, prioridade: finalPriority }) }).then(sync);
  };

  if (!user || currentScreen === 'login') return <LoginScreen onLogin={handleLogin} />;
  if (currentScreen === 'change_password') return <ChangePasswordScreen user={user} onPasswordChanged={handlePasswordChanged} />;
  if (currentScreen === 'admin') return <AdminPanel onBack={() => setCurrentScreen('board')} currentUsers={allUsers} refreshUsers={fetchUsers} />;

  return (
    <div className="relative h-[100dvh] font-sans overflow-hidden" onMouseMove={e => { setShowLeftArrow(e.clientX < 80); setShowRightArrow(e.clientX > window.innerWidth - 80); }}>
      <div className="fixed inset-0 bg-gradient-to-br from-emerald-800 via-teal-900 to-emerald-900 -z-10" />

      {modal && <CardModal card={modal.card} col={cols.find(c => c.id === modal.status)} user={user} allUsers={allUsers} onClose={() => setModal(null)} onSave={handleSaveCard} onDelete={id => authFetch(`${API}/cards/${id}`, { method: 'DELETE' }).then(() => { setModal(null); sync(); })} />}

      <div
        className="fixed top-0 left-0 right-0 h-4 z-[120]"
        onMouseEnter={() => setHeaderVisible(true)}
      />
      <header
        className={`fixed top-0 left-0 right-0 z-[110] flex flex-col sm:flex-row justify-between items-center gap-3 bg-white/10 p-3 md:p-4 rounded-b-2xl backdrop-blur-md transition-transform duration-300 ${headerVisible ? 'translate-y-0' : '-translate-y-full'}`}
        onMouseEnter={() => setHeaderVisible(true)}
        onMouseLeave={() => setHeaderVisible(false)}
      >
        <div className="w-full flex justify-between items-center sm:w-auto">
          <h1 className="text-2xl md:text-3xl font-black text-white italic tracking-tighter uppercase">Kyndo</h1>
          <button onClick={sync} className="sm:hidden flex items-center justify-center p-2 bg-white/20 hover:bg-white/30 rounded-xl text-white border border-white/10 shadow-lg">
            <RefreshCw size={16} className={isSyncing ? "animate-spin" : ""} />
          </button>
        </div>
        
        <div className="flex flex-wrap items-center gap-2 md:gap-4 w-full sm:w-auto justify-end relative">
          <button onClick={toggleFullscreen} className="hidden sm:flex items-center justify-center p-2 px-3 bg-white/20 hover:bg-white/30 rounded-xl text-white border border-white/10 transition-colors shadow-lg" title={isFullscreen ? 'Sair da tela cheia' : 'Tela cheia'}>
            {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
          </button>
          <button onClick={sync} className="hidden sm:flex items-center justify-center p-2 px-3 bg-white/20 hover:bg-white/30 rounded-xl text-white border border-white/10 transition-colors shadow-lg">
            <RefreshCw size={18} className={isSyncing ? "animate-spin" : ""} />
          </button>

          <div className="hidden sm:flex items-center bg-white/10 rounded-xl border border-white/10 p-0.5 shadow-lg">
            <button onClick={() => setActiveView('board')} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${activeView === 'board' ? 'bg-white text-emerald-800 shadow' : 'text-white hover:bg-white/10'}`}>
              Quadro
            </button>
            <button onClick={() => setActiveView('cronograma')} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${activeView === 'cronograma' ? 'bg-white text-emerald-800 shadow' : 'text-white hover:bg-white/10'}`}>
              Cronograma
            </button>
            <button onClick={() => setActiveView('notas')} className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${activeView === 'notas' ? 'bg-white text-emerald-800 shadow' : 'text-white hover:bg-white/10'}`}>
              Notas
            </button>
          </div>

          <div className="relative flex-grow sm:flex-none">
            <div onClick={() => setFiltroAberto(!filtroAberto)} className="flex items-center justify-between gap-2 bg-white/90 p-2 md:px-4 rounded-xl text-gray-800 shadow-lg border border-white/20 cursor-pointer h-full transition-colors hover:bg-white">
              <div className="flex items-center gap-2">
                <Filter size={16} className="text-emerald-600 shrink-0" />
                <span className="font-bold text-xs md:text-sm truncate">
                  {filtroAtivo === 'todas' ? 'Todas Demandas' : filtroAtivo === 'minhas' ? 'Minhas Demandas' : `Prio: ${filtroAtivo}`}
                  {ordenacao !== 'prioridade_desc' && <span className="ml-1 text-emerald-600">{ordenacao === 'prioridade_asc' ? '↑' : '–'}</span>}
                </span>
              </div>
              <ChevronDown size={14} className="text-gray-500 shrink-0" />
            </div>
            
            {filtroAberto && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setFiltroAberto(false)} />
                <div className="absolute top-full mt-2 right-0 sm:right-auto w-full min-w-[180px] bg-white rounded-xl shadow-2xl border border-gray-200 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2">
                  <div className="px-3 pt-2 pb-1 text-[10px] font-black text-gray-400 uppercase tracking-widest">Filtrar</div>
                  {[{ val: 'todas', label: 'Todas as Demandas' }, { val: 'minhas', label: 'Minhas Demandas' }, { divider: true }, { val: 'Baixa', label: 'Prioridade: Baixa' }, { val: 'Normal', label: 'Prioridade: Normal' }, { val: 'Alta', label: 'Prioridade: Alta' }, { val: 'Urgente', label: 'Prioridade: Urgente' }].map((opcao, i) =>
                    opcao.divider ? (<div key={`div-${i}`} className="h-px bg-gray-100 my-1 mx-2" />) : (
                      <div key={opcao.val} onClick={() => { setFiltroAtivo(opcao.val); setFiltroAberto(false); }} className={`p-3 px-4 hover:bg-emerald-50 cursor-pointer text-xs md:text-sm font-bold transition-colors ${filtroAtivo === opcao.val ? 'text-emerald-600 bg-emerald-50/50' : 'text-gray-700'}`}>
                        {opcao.label}
                      </div>
                    )
                  )}
                  <div className="h-px bg-gray-100 my-1 mx-2" />
                  <div className="px-3 pt-2 pb-1 text-[10px] font-black text-gray-400 uppercase tracking-widest">Ordenação</div>
                  {[{ val: 'prioridade_desc', label: '↓ Maior prioridade primeiro' }, { val: 'prioridade_asc', label: '↑ Menor prioridade primeiro' }, { val: 'padrao', label: '– Sem ordenação' }].map(opcao => (
                    <div key={opcao.val} onClick={() => { setOrdenacao(opcao.val); setFiltroAberto(false); }} className={`p-3 px-4 hover:bg-emerald-50 cursor-pointer text-xs md:text-sm font-bold transition-colors ${ordenacao === opcao.val ? 'text-emerald-600 bg-emerald-50/50' : 'text-gray-700'}`}>
                      {opcao.label}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="flex items-center gap-2 md:gap-4 bg-white/20 p-2 md:px-4 rounded-xl text-white border border-white/10">
            <div className="flex items-center gap-1 md:gap-2">
              <User size={16} />
              <span className="font-bold text-xs md:text-sm truncate max-w-[80px] md:max-w-none">{user.nome}</span>
            </div>
            
            {user.role === 'superadmin' && (
              <button onClick={() => { setCurrentScreen('admin'); fetchUsers(); }} className="text-[10px] md:text-xs bg-orange-500 hover:bg-orange-600 px-2 md:px-3 py-1 rounded font-bold uppercase transition-colors shadow-md">
                Admin
              </button>
            )}

            <button onClick={handleLogout} className="text-red-300 hover:text-red-100 p-1 ml-1 md:ml-2 transition-colors border-l border-white/20 pl-2 md:pl-4" title="Sair">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      <button
        onClick={() => boardRef.current && (boardRef.current.scrollLeft -= 320)}
        className={`fixed left-2 top-1/2 -translate-y-1/2 z-[100] w-10 h-16 bg-black/40 text-white rounded-xl flex items-center justify-center transition-all duration-200 backdrop-blur-sm pointer-events-auto ${showLeftArrow && activeView === 'board' ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        aria-label="Rolar esquerda"
      >
        <ChevronLeft size={28} />
      </button>
      <button
        onClick={() => boardRef.current && (boardRef.current.scrollLeft += 320)}
        className={`fixed right-2 top-1/2 -translate-y-1/2 z-[100] w-10 h-16 bg-black/40 text-white rounded-xl flex items-center justify-center transition-all duration-200 backdrop-blur-sm ${showRightArrow && activeView === 'board' ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        aria-label="Rolar direita"
      >
        <ChevronRight size={28} />
      </button>

      {activeView === 'cronograma' && (
        <CronogramaView cards={cards} allUsers={allUsers} setModal={setModal} />
      )}
      {activeView === 'notas' && (
        <NotasView user={user} />
      )}

      <div ref={boardRef} className={`h-full overflow-y-auto overflow-x-hidden md:overflow-x-auto md:overflow-y-hidden p-3 md:p-8 custom-scrollbar ${activeView !== 'board' ? 'invisible pointer-events-none absolute' : ''}`}>
        <DragDropContext onDragEnd={onDragEnd}>
          <div className="relative min-h-full w-full">
            <Droppable droppableId="board" direction="horizontal" type="column">
            {(provided) => (
              <div {...provided.droppableProps} ref={provided.innerRef} className="flex flex-col md:flex-row gap-4 items-start w-full">
                
                {cols.map((col, index) => (
                  <Draggable key={col.id} draggableId={col.id} index={index} isDragDisabled={user.role !== 'admin' && user.role !== 'superadmin'}>
                    {(p, snapshot) => (
                      <div ref={p.innerRef} {...p.draggableProps} className={`w-full md:flex-1 md:min-w-[220px] flex flex-col rounded-2xl shadow-xl min-h-[120px] max-h-[calc(100dvh-4rem)] transition-transform ${snapshot.isDragging ? 'rotate-[2deg] scale-105 z-50 ring-2 ring-emerald-400' : ''}`} style={{ ...p.draggableProps.style, backgroundColor: col.cor }}>
                        
                        <div {...p.dragHandleProps} className="p-3 pl-4 flex items-center justify-between gap-2 relative shrink-0">
                          <div className="flex items-center gap-2">
                            {col.publica ? <Unlock size={12} className="text-green-600"/> : <Lock size={12} className="text-gray-500"/>}
                            <input disabled={user.role !== 'admin' && user.role !== 'superadmin'} value={col.titulo} onChange={e => {
                                const newCol = {...col, titulo: e.target.value};
                                authFetch(`${API}/columns/${col.id}`, { method: 'PUT', body: JSON.stringify(newCol) }).then(sync);
                            }} className="bg-transparent font-bold text-gray-800 text-sm w-full outline-none uppercase tracking-widest" />
                          </div>
                          {(user.role === 'admin' || user.role === 'superadmin') && <button onClick={() => setActiveMenu(activeMenu === col.id ? null : col.id)} className="p-1 hover:bg-black/5 rounded transition-colors"><MoreHorizontal size={18}/></button>}
                          {activeMenu === col.id && <ListActionsMenu col={col} user={user} onClose={() => setActiveMenu(null)} onAddCard={() => setModal({status: col.id})} onArchiveList={() => {authFetch(`${API}/columns/${col.id}`, { method: 'PUT', body: JSON.stringify({...col, arquivado: true}) }).then(sync);}} onUpdateCol={(data) => {authFetch(`${API}/columns/${col.id}`, { method: 'PUT', body: JSON.stringify(data) }).then(sync);}} />}
                        </div>

                        <Droppable droppableId={col.id} type="card">
                          {(dp) => (
                            <div {...dp.droppableProps} ref={dp.innerRef} className="px-2 pb-2 flex-grow overflow-y-auto space-y-2 custom-scrollbar min-h-[50px]">
                              {Object.values(cards)
                                .filter(k => k.status === col.id)
                                .filter(k => {
                                  if (filtroAtivo === 'minhas') return k.autor === user.nome || (k.responsaveis || []).includes(user.nome);
                                  if (['Baixa', 'Normal', 'Alta', 'Urgente'].includes(filtroAtivo)) return k.prioridade === filtroAtivo;
                                  return true;
                                })
                                .sort((a, b) => {
                                  if (ordenacao === 'prioridade_desc') return (PRIORIDADE_ORDEM[b.prioridade] || 0) - (PRIORIDADE_ORDEM[a.prioridade] || 0);
                                  if (ordenacao === 'prioridade_asc') return (PRIORIDADE_ORDEM[a.prioridade] || 0) - (PRIORIDADE_ORDEM[b.prioridade] || 0);
                                  return 0;
                                })
                                .map((card, ki) => {
                                const clCard = card.checklist || [];
                                const totalEtapas = clCard.length;
                                const progresso = totalEtapas > 0 ? Math.round(
                                  clCard.reduce((acc, item) => {
                                    const subs = item.subetapas || [];
                                    return acc + (subs.length === 0 ? (item.concluido ? 1 : 0) : subs.filter(s => s.concluido).length / subs.length);
                                  }, 0) / totalEtapas * 100
                                ) : 0;
                                const concluidas = clCard.filter(i => i.concluido).length;
                                const isAdmin = user.role === 'admin' || user.role === 'superadmin';
                                const qtdComentarios = card.comentarios?.length || 0;

                                const stylePrioridade = PRIORIDADE_CARD_STYLE[card.prioridade || 'Normal'];

                                return (
                                  <Draggable key={card.id} draggableId={card.id} index={ki} isDragDisabled={!isAdmin}>
                                    {(kp) => (
                                      <div ref={kp.innerRef} {...kp.draggableProps} {...kp.dragHandleProps} onClick={() => setModal({card, status: col.id})} className={`p-4 rounded-xl cursor-pointer hover:opacity-80 transition-all flex flex-col gap-2 ${stylePrioridade}`}>

                                        <div className="flex justify-between items-start">
                                          <span className={`text-xs uppercase px-2 py-0.5 rounded ${PRIORIDADES_BADGE[card.prioridade || 'Normal']}`}>
                                            {card.prioridade || 'Normal'}
                                          </span>
                                          {card.prazo && (
                                            <span className="flex items-center gap-1 text-xs text-orange-700 bg-orange-100 font-bold px-1.5 py-0.5 rounded">
                                              <Calendar size={12} /> {formatarData(card.prazo)}
                                            </span>
                                          )}
                                        </div>

                                        <p className="text-base font-bold text-gray-800 leading-tight">{card.titulo}</p>
                                        
                                        {totalEtapas > 0 && progresso > 0 && (
                                          <div>
                                            <div className="flex justify-between items-center mb-1">
                                              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Progresso</span>
                                              <span className="text-xl font-black text-gray-800">{progresso}%</span>
                                            </div>
                                            <div className="w-full h-2 bg-gray-300/50 rounded-full overflow-hidden">
                                              <div className={`h-full transition-all duration-300 ${progresso === 100 ? 'bg-emerald-600' : 'bg-teal-500'}`} style={{ width: `${progresso}%` }} />
                                            </div>
                                          </div>
                                        )}

                                        <div className="flex justify-between items-center mt-1 border-t pt-2 border-black/10">
                                          <div className="flex flex-wrap items-center gap-1">
                                            <span className="text-xs text-gray-600 uppercase font-bold">Resp.:</span>
                                            {(card.responsaveis?.length > 0 ? card.responsaveis : [card.autor]).filter(Boolean).map(nome => (
                                              <span key={nome} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${userColor(nome)}`}>{nome}</span>
                                            ))}
                                          </div>
                                          <div className="flex items-center gap-2">
                                            {card.github_url && (
                                              <a href={card.github_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} title="Abrir repositório no GitHub" className="text-gray-700 hover:text-black transition-colors">
                                                <GitHubIcon size={14} />
                                              </a>
                                            )}
                                            {qtdComentarios > 0 && (
                                              <div className="flex items-center gap-1 text-xs text-gray-600 font-bold bg-white/60 px-1.5 rounded">
                                                <MessageSquare size={12} /> {qtdComentarios}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                    )}
                                  </Draggable>
                                )
                              })}
                              {dp.placeholder}
                            </div>
                          )}
                        </Droppable>

                        {(user.role === 'admin' || user.role === 'superadmin' || col.publica) && (
                          <button onClick={() => setModal({status: col.id})} className="m-2 mt-auto shrink-0 p-2 text-xs font-bold text-gray-500 hover:bg-black/5 rounded-xl flex items-center gap-2 transition-colors">
                            <Plus size={16}/> Sugerir demanda
                          </button>
                        )}
                      </div>
                    )}
                  </Draggable>
                ))}
                
                {provided.placeholder}

              </div>
            )}
            </Droppable>

            {(user.role === 'admin' || user.role === 'superadmin') && (
              <button onClick={() => { authFetch(`${API}/columns`, {method: 'POST', body: JSON.stringify({id: `col-${Date.now()}`, titulo: 'Nova Coluna', cor: '#ebecf0', ordem: cols.length, publica: false, auto_andamento: false, auto_concluido: false})}).then(sync); }} className="hidden md:flex absolute top-0 w-64 h-16 bg-white/10 hover:bg-white/20 border-2 border-white/30 border-dashed rounded-2xl items-center justify-center text-white transition-all cursor-pointer" style={{ left: 'calc(100% + 3rem)' }}>
                <Plus size={20} className="mr-2" />
                <span className="font-bold text-sm">Adicionar Coluna</span>
              </button>
            )}
          </div>
        </DragDropContext>
      </div>
    </div>
  );
}