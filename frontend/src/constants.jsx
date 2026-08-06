import React from 'react';

export const USER_COLORS = [
  'bg-blue-100 text-blue-700',
  'bg-purple-100 text-purple-700',
  'bg-orange-100 text-orange-700',
  'bg-pink-100 text-pink-700',
  'bg-teal-100 text-teal-700',
  'bg-yellow-100 text-yellow-800',
  'bg-red-100 text-red-700',
  'bg-indigo-100 text-indigo-700',
];

export const userColor = (nome = '') => {
  let hash = 0;
  for (const c of nome) hash += c.charCodeAt(0);
  return USER_COLORS[hash % USER_COLORS.length];
};

export const PRIORIDADES_BADGE = {
  'Baixa':   'bg-green-600 text-white shadow-sm',
  'Normal':  'bg-yellow-400 text-gray-900 shadow-sm',
  'Alta':    'bg-orange-500 text-white shadow-sm',
  'Urgente': 'bg-red-600 text-white font-black shadow-sm',
};

export const PRIORIDADE_CARD_STYLE = {
  'Baixa':   'bg-green-100 border-green-500 border-2',
  'Normal':  'bg-yellow-50 border-yellow-400 border-2',
  'Alta':    'bg-orange-100 border-orange-500 border-2',
  'Urgente': 'bg-red-200 border-red-600 border-2 shadow-md shadow-red-300/50',
};

export const PRIORIDADE_ORDEM = { 'Urgente': 4, 'Alta': 3, 'Normal': 2, 'Baixa': 1 };

export const NODE_COLORS = {
  blue:    { bg: '#dbeafe', border: '#2563eb', text: '#1e3a8a' },
  emerald: { bg: '#d1fae5', border: '#059669', text: '#064e3b' },
  purple:  { bg: '#ede9fe', border: '#7c3aed', text: '#4c1d95' },
  orange:  { bg: '#ffedd5', border: '#ea580c', text: '#7c2d12' },
  pink:    { bg: '#fce7f3', border: '#db2777', text: '#831843' },
  yellow:  { bg: '#fef9c3', border: '#ca8a04', text: '#713f12' },
};

export const DRAW_W = 2400;
export const DRAW_H = 1400;
export const DRAW_COLORS = ['#ffffff','#f87171','#fb923c','#facc15','#4ade80','#60a5fa','#a78bfa','#f472b6','#94a3b8','#000000'];
export const DRAW_SIZES  = [2, 5, 10, 22];

export const hasPermission = (user, key) => (user?.permissions || []).includes(key);

// Cargos (roles) a given user holds, excluding the baseline "Usuário" cargo —
// used to render Discord-style chips next to comment/suggestion authors.
export function autorRoleChips(autorNome, allUsers) {
  const autor = (allUsers || []).find(u => u.nome === autorNome);
  const roles = (autor?.roles || []).filter(r => r.nome !== 'Usuário');
  if (roles.length === 0) return null;
  return roles.map(r => (
    <span key={r.id} className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider text-white" style={{ backgroundColor: r.cor }}>{r.nome}</span>
  ));
}

export function formatarData(dataISO) {
  if (!dataISO) return '';
  const [ano, mes, dia] = dataISO.split('-');
  return `${dia}/${mes}/${ano}`;
}

export function renderTextWithLinks(text) {
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

const MENTION_TOKEN_RE = /(@\[[^\]]+\]\((?:card|etapa):[\w-]+\))/g;
const MENTION_PARSE_RE = /^@\[([^\]]+)\]\((card|etapa):([\w-]+)\)$/;

export function mentionToken(tipo, id, label) {
  return `@[${label}](${tipo}:${id})`;
}

export function renderSuggestionText(text, { onCardClick, onEtapaClick } = {}) {
  if (!text) return null;
  const parts = text.split(MENTION_TOKEN_RE);
  return parts.map((part, i) => {
    const m = part.match(MENTION_PARSE_RE);
    if (!m) return part;
    const [, label, tipo, id] = m;
    return (
      <button
        key={i}
        type="button"
        onClick={() => (tipo === 'card' ? onCardClick?.(id) : onEtapaClick?.(id))}
        className="inline-flex items-center gap-1 px-1.5 py-0.5 mx-0.5 rounded bg-emerald-100 text-emerald-700 text-xs font-bold hover:bg-emerald-200 align-baseline"
      >
        {label}
      </button>
    );
  });
}

export const GitHubIcon = ({ size = 20, className = '' }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" className={className} aria-hidden="true">
    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
  </svg>
);
