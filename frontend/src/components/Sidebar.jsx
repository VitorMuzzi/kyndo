import React from 'react';
import { TELA_CONFIG } from '../constants.jsx';
import { LogOut, User, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';

function Item({ tela, ativa, recolhido, onClick, ponto, dica }) {
  const Icone = tela.icone;
  return (
    <button onClick={onClick} title={recolhido ? (dica || tela.label) : dica}
      className={`relative w-full flex items-center gap-3 rounded-xl text-sm font-bold transition-colors ${recolhido ? 'justify-center p-2.5' : 'px-3 py-2.5'} ${ativa
        ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow'
        : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'}`}>
      <Icone size={18} className="shrink-0"/>
      {!recolhido && <span className="truncate">{tela.label}</span>}
      {ponto && <span className={`absolute w-2 h-2 bg-red-500 rounded-full ring-2 ring-slate-900 ${recolhido ? 'top-1.5 right-1.5' : 'top-1/2 -translate-y-1/2 right-3'}`}/>}
    </button>
  );
}

// Menu lateral: no computador fica fixo à esquerda e pode ser recolhido só
// para os ícones; no celular vira uma gaveta aberta pelo botão de menu.
export default function Sidebar({ telas, ativa, onSelecionar, user, pedidosSenha, pontos = {}, onSair, recolhido, onAlternarRecolhido, gaveta = false, onFecharGaveta }) {
  const curta = recolhido && !gaveta;
  return (
    <nav className={`h-full flex flex-col bg-slate-900/95 border-r border-slate-800 transition-[width] duration-200 ${gaveta ? 'w-64' : curta ? 'w-[4.5rem]' : 'w-56'}`}>
      {/* Nome e botão de recolher/expandir na mesma linha, nos dois tamanhos:
          o botão fica sempre no canto direito do topo. */}
      <div className={`h-14 shrink-0 flex items-center justify-between gap-1 border-b border-slate-800 ${curta ? 'px-2' : 'px-4'}`}>
        <span className="text-2xl font-black text-white italic tracking-tighter uppercase">{curta ? 'K' : 'Kyndo'}</span>
        {gaveta ? (
          <button onClick={onFecharGaveta} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10" title="Fechar menu"><X size={18}/></button>
        ) : (
          <button onClick={onAlternarRecolhido} className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10" title={curta ? 'Expandir menu' : 'Recolher menu'}>
            {curta ? <PanelLeftOpen size={18}/> : <PanelLeftClose size={18}/>}
          </button>
        )}
      </div>

      <div className={`flex-1 overflow-y-auto custom-scrollbar space-y-1 ${curta ? 'p-2' : 'p-3'}`}>
        {telas.map(t => (
          <Item key={t.key} tela={t} ativa={ativa === t.key} recolhido={curta} onClick={() => onSelecionar(t.key)}
            ponto={pontos[t.key] > 0} dica={pontos[t.key] > 0 ? `${t.label} — ${pontos[t.key]} novidade(s)` : undefined}/>
        ))}
      </div>

      <div className={`shrink-0 border-t border-slate-800 space-y-1 ${curta ? 'p-2' : 'p-3'}`}>
        <Item tela={TELA_CONFIG} ativa={ativa === TELA_CONFIG.key} recolhido={curta} onClick={() => onSelecionar(TELA_CONFIG.key)}
          ponto={pedidosSenha > 0} dica={pedidosSenha > 0 ? `Configurações — ${pedidosSenha} pedido(s) de nova senha` : undefined}/>
        <div className={`flex items-center gap-2 rounded-xl text-slate-300 ${curta ? 'flex-col py-1' : 'px-3 py-2'}`}>
          <User size={16} className="shrink-0 text-slate-500" title={user.nome}/>
          {!curta && <span className="flex-1 min-w-0 truncate text-sm font-bold" title={user.nome}>{user.nome}</span>}
          <button onClick={onSair} className="p-1.5 rounded-lg text-red-300 hover:text-red-100 hover:bg-red-500/10 transition-colors" title="Sair">
            <LogOut size={16}/>
          </button>
        </div>
      </div>
    </nav>
  );
}
