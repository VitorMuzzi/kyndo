import React, { useState, useMemo } from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { GripVertical, ChevronUp, ChevronDown, IndentIncrease, IndentDecrease, Check, Trash2, RotateCcw } from 'lucide-react';
import {
  achatar, montarArvore, tamanhoDoBloco, moverBloco,
  indentar, desindentar, moverParaCima, moverParaBaixo, removerBloco,
  podeIndentar, podeDesindentar,
} from '../etapasTree.js';

// Modo de organização das etapas. Separado da visualização normal de
// propósito: aqui não existe caixa de concluir, então não dá pra marcar etapa
// sem querer enquanto você arruma a lista.
//
// A aritmética de árvore/índice vive em etapasTree.js pra ser testável fora
// do React — aqui só tem UI e estado.

export default function EtapasEditor({ checklist, onAplicar, onCancelar, novoId, usuario }) {
  const original = useMemo(() => achatar(checklist), [checklist]);
  const [linhas, setLinhas] = useState(original);
  const [editandoId, setEditandoId] = useState(null);
  const [textoEdicao, setTextoEdicao] = useState('');
  const [novoTexto, setNovoTexto] = useState('');

  const mudou = JSON.stringify(linhas) !== JSON.stringify(original);

  const renomear = (i, texto) =>
    setLinhas(prev => prev.map((l, idx) => idx === i ? { ...l, texto } : l));

  const aoIndentar = (i) => {
    // Perder observação sem avisar seria pior que bloquear: sub-etapa não
    // guarda `notas` no modelo do card, então o texto vai embora de vez.
    if ((linhas[i].notas || '').trim()) {
      const ok = window.confirm(
        `"${linhas[i].texto}" tem observações, e sub-etapa não guarda observações.\n\n` +
        'Indentar vai descartar esse texto. Continuar?'
      );
      if (!ok) return;
    }
    setLinhas(prev => indentar(prev, i));
  };

  const aoRemover = (i) => {
    const linha = linhas[i];
    const tam = tamanhoDoBloco(linhas, i);
    const filhas = tam - 1;
    const oQue = linha.nivel === 1 ? 'sub-etapa' : 'etapa';

    let msg = `Excluir a ${oQue} "${linha.texto}"?`;
    if (filhas > 0) {
      msg += `\n\nAs ${filhas} sub-etapa(s) dela vão junto:\n` +
        linhas.slice(i + 1, i + tam).map(l => `  • ${l.texto}`).join('\n');
    }
    if ((linha.notas || '').trim()) {
      msg += '\n\nAs observações desta etapa também serão perdidas.';
    }
    if (!window.confirm(msg)) return;

    setLinhas(prev => removerBloco(prev, i));
  };

  const adicionar = () => {
    const texto = novoTexto.trim();
    if (!texto) return;
    setLinhas(prev => [...prev, { id: novoId('sub'), texto, concluido: false, criador: usuario, nivel: 0 }]);
    setNovoTexto('');
  };

  const onDragEnd = (r) => {
    if (!r.destination || r.destination.index === r.source.index) return;
    setLinhas(prev => moverBloco(prev, r.source.index, r.destination.index));
  };

  const totalEtapas = linhas.filter(l => l.nivel === 0).length;

  return (
    <div className="border border-emerald-700/50 bg-slate-950/60 rounded-xl p-3 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Editando etapas</p>
          <p className="text-[10px] text-slate-500 mt-0.5">
            {totalEtapas} etapa(s), {linhas.length - totalEtapas} sub-etapa(s) · arraste pela alça ou use as setas
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {mudou && (
            <button onClick={() => setLinhas(original)} title="Desfazer todas as mudanças"
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] font-bold text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors">
              <RotateCcw size={12}/> Desfazer
            </button>
          )}
          <button onClick={onCancelar}
            className="px-2.5 py-1.5 rounded-lg text-[10px] font-bold text-slate-300 hover:bg-slate-800 transition-colors">
            Cancelar
          </button>
          <button onClick={() => onAplicar(montarArvore(linhas))}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition-colors">
            <Check size={12}/> Concluir
          </button>
        </div>
      </div>

      {linhas.length === 0 ? (
        <p className="text-xs text-slate-500 text-center py-3">Nenhuma etapa ainda. Adicione abaixo.</p>
      ) : (
        <DragDropContext onDragEnd={onDragEnd}>
          <Droppable droppableId="etapas-editor">
            {(dropProvided) => (
              <div ref={dropProvided.innerRef} {...dropProvided.droppableProps} className="space-y-0.5">
                {linhas.map((linha, i) => {
                  const tam = tamanhoDoBloco(linhas, i);
                  return (
                    <Draggable key={linha.id} draggableId={String(linha.id)} index={i}>
                      {(dragProvided, snapshot) => (
                        <div
                          ref={dragProvided.innerRef}
                          {...dragProvided.draggableProps}
                          style={{ ...dragProvided.draggableProps.style, marginLeft: linha.nivel === 1 ? 22 : 0 }}
                          className={`flex items-center gap-1 rounded-lg px-1.5 py-1 group/linha ${
                            snapshot.isDragging
                              ? 'bg-slate-800 ring-1 ring-emerald-500 shadow-xl'
                              : 'bg-slate-900/70 hover:bg-slate-800/70'
                          }`}
                        >
                          <span {...dragProvided.dragHandleProps} title="Arrastar"
                            className="shrink-0 text-slate-600 hover:text-slate-300 cursor-grab active:cursor-grabbing p-0.5 touch-none">
                            <GripVertical size={14}/>
                          </span>

                          {linha.nivel === 1 && <span className="shrink-0 text-slate-600 text-xs select-none">└</span>}

                          {editandoId === linha.id ? (
                            <input
                              autoFocus value={textoEdicao}
                              onChange={e => setTextoEdicao(e.target.value)}
                              onBlur={() => { if (textoEdicao.trim()) renomear(i, textoEdicao.trim()); setEditandoId(null); }}
                              onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') setEditandoId(null); }}
                              className="flex-1 min-w-0 text-xs bg-transparent border-b border-emerald-400 outline-none text-slate-100 py-0.5"
                            />
                          ) : (
                            <span
                              onClick={() => { setEditandoId(linha.id); setTextoEdicao(linha.texto); }}
                              title={linha.texto}
                              className={`flex-1 min-w-0 text-xs truncate cursor-text hover:text-emerald-400 ${
                                linha.nivel === 0 ? 'text-slate-100 font-medium' : 'text-slate-300'
                              }`}
                            >
                              {linha.texto}
                            </span>
                          )}

                          {/* O arrasto move o bloco inteiro, mas o dnd só anima uma linha —
                              o contador deixa isso explícito em vez de surpreender. */}
                          {tam > 1 && (
                            <span className={`shrink-0 text-[9px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap ${
                              snapshot.isDragging ? 'text-emerald-300 bg-emerald-500/20' : 'text-slate-500 bg-slate-800'
                            }`} title={`Move junto com ${tam - 1} sub-etapa(s)`}>
                              +{tam - 1}
                            </span>
                          )}
                          {linha.concluido && <span className="shrink-0 text-[10px] font-bold text-emerald-500" title="Concluída">✓</span>}
                          {(linha.notas || '').trim() && <span className="shrink-0 text-[10px] text-amber-400" title="Tem observações">◆</span>}

                          <div className="flex items-center shrink-0 opacity-50 group-hover/linha:opacity-100 transition-opacity">
                            <button onClick={() => setLinhas(prev => moverParaCima(prev, i))} disabled={i === 0}
                              title="Mover pra cima"
                              className="p-0.5 text-slate-400 hover:text-emerald-400 disabled:opacity-20 disabled:hover:text-slate-400">
                              <ChevronUp size={13}/>
                            </button>
                            <button onClick={() => setLinhas(prev => moverParaBaixo(prev, i))} disabled={i + tam >= linhas.length}
                              title="Mover pra baixo"
                              className="p-0.5 text-slate-400 hover:text-emerald-400 disabled:opacity-20 disabled:hover:text-slate-400">
                              <ChevronDown size={13}/>
                            </button>
                            <button onClick={() => setLinhas(prev => desindentar(prev, i))} disabled={!podeDesindentar(linhas, i)}
                              title="Desindentar — virar etapa"
                              className="p-0.5 text-slate-400 hover:text-emerald-400 disabled:opacity-20 disabled:hover:text-slate-400">
                              <IndentDecrease size={13}/>
                            </button>
                            <button onClick={() => aoIndentar(i)} disabled={!podeIndentar(linhas, i)}
                              title="Indentar — virar sub-etapa da de cima"
                              className="p-0.5 text-slate-400 hover:text-emerald-400 disabled:opacity-20 disabled:hover:text-slate-400">
                              <IndentIncrease size={13}/>
                            </button>
                            <button onClick={() => aoRemover(i)} title="Remover"
                              className="p-0.5 text-red-400 hover:text-red-300 ml-0.5">
                              <Trash2 size={13}/>
                            </button>
                          </div>
                        </div>
                      )}
                    </Draggable>
                  );
                })}
                {dropProvided.placeholder}
              </div>
            )}
          </Droppable>
        </DragDropContext>
      )}

      <div className="flex gap-1.5 pt-1">
        <input
          value={novoTexto}
          onChange={e => setNovoTexto(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') adicionar(); }}
          placeholder="Adicionar etapa..."
          className="flex-1 min-w-0 text-xs bg-slate-800 text-slate-100 border border-slate-700 rounded-lg px-2 py-1.5 outline-none focus:border-emerald-400"
        />
        <button onClick={adicionar}
          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors">
          Add
        </button>
      </div>

      <p className="text-[10px] text-slate-600 leading-relaxed">
        Concluir aplica no card, mas ainda não salva — precisa do
        <span className="font-bold text-slate-400"> Salvar Tudo</span> depois.
      </p>
    </div>
  );
}
