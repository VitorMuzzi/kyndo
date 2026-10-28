// Cronômetro de trabalho: formatação e o relógio que avança na tela.
//
// O tempo de verdade corre no servidor. A tela só recebe "quanto já passou"
// (decorrido_segundos) na hora em que buscou e soma o que passou desde então
// — nunca compara com o relógio do próprio computador, que pode estar
// desacertado em relação ao do servidor.

import { useEffect, useState } from 'react';
import { API, authFetch } from './api.js';

const dois = (n) => String(n).padStart(2, '0');

// 01:05:09 — pro relógio que está correndo.
export const formatarRelogio = (segundos) => {
  const s = Math.max(0, Math.floor(segundos));
  return `${dois(Math.floor(s / 3600))}:${dois(Math.floor((s % 3600) / 60))}:${dois(s % 60)}`;
};

// 1h 05min / 12min / 40s — pros totais.
export const formatarDuracao = (segundos) => {
  const s = Math.max(0, Math.floor(segundos || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${dois(m)}min`;
  if (m > 0) return `${m}min`;
  return `${s}s`;
};

// Busca o cronômetro em andamento de quem está logado; null se não houver.
export const buscarCronometroAtual = async () => {
  const res = await authFetch(`${API}/tempo/atual`);
  if (!res.ok) return undefined;  // undefined = não deu pra saber; não apaga o que a tela já mostra
  const data = await res.json();
  return data ? { ...data, recebidoEm: Date.now() } : null;
};

export const iniciarCronometro = async (cardId, itemId) => {
  const res = await authFetch(`${API}/cards/${cardId}/tempo/iniciar`, {
    method: 'POST', body: JSON.stringify({ item_id: itemId || null }),
  });
  if (!res.ok) {
    const corpo = await res.json().catch(() => ({}));
    throw new Error(corpo.detail || 'Não foi possível iniciar o cronômetro.');
  }
  return { ...(await res.json()), recebidoEm: Date.now() };
};

export const pararCronometro = async () => {
  const res = await authFetch(`${API}/tempo/parar`, { method: 'POST' });
  if (!res.ok) throw new Error('Não foi possível parar o cronômetro.');
};

// "Agora" que avança a cada segundo enquanto `ativo` — fica em estado porque
// ler Date.now() durante a renderização deixa o componente impuro.
export const useAgora = (ativo) => {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    if (!ativo) return;
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [ativo]);
  return agora;
};

// Segundos que `desde` (um objeto com recebidoEm) acumulou até `agora`. O
// max(0) cobre o primeiro segundo, em que `agora` ainda pode ser anterior à busca.
export const segundosDesde = (desde, agora) => Math.max(0, agora - desde.recebidoEm) / 1000;

// Segundos decorridos de um cronômetro, avançando a cada segundo na tela.
export const useDecorrido = (cronometro) => {
  const agora = useAgora(!!cronometro);
  return cronometro ? cronometro.decorrido_segundos + segundosDesde(cronometro, agora) : 0;
};
