import React, { useState, useEffect, useRef } from 'react';

export default function TextEditor({ noteId, conteudo, allNotes, onChange, onOpenNote, readOnly = false }) {
  const [local, setLocal]     = useState(conteudo);
  const [editing, setEditing] = useState(!conteudo && !readOnly);
  const timer     = useRef(null);
  const areaRef   = useRef(null);

  useEffect(() => {
    setLocal(conteudo);
    setEditing(!conteudo && !readOnly);
  }, [noteId]);

  const handle = (e) => {
    const v = e.target.value;
    setLocal(v);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange(v), 700);
  };

  const enterEdit = () => {
    if (readOnly) return;
    setEditing(true);
    setTimeout(() => areaRef.current?.focus(), 0);
  };

  const leaveEdit = () => {
    if (local) setEditing(false);
  };

  const renderContent = (text) => {
    if (!text) return <span className="text-white/20 select-none">Clique para editar...</span>;
    const parts = text.split(/(\[\[[^\]]+\]\])/g);
    return parts.map((part, i) => {
      const m = part.match(/^\[\[([^\]]+)\]\]$/);
      if (m) {
        const name   = m[1].trim();
        const linked = allNotes.find(n => n.titulo?.trim().toLowerCase() === name.toLowerCase());
        return (
          <span key={i}
            onClick={linked ? (e) => { e.stopPropagation(); onOpenNote(linked.id); } : undefined}
            title={linked ? `Abrir: ${linked.titulo}` : 'Nota não encontrada'}
            className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-xs font-bold mx-0.5 align-baseline ${
              linked
                ? 'bg-emerald-500/25 text-emerald-300 hover:bg-emerald-500/40 cursor-pointer underline underline-offset-2'
                : 'bg-white/8 text-white/30 line-through cursor-default'
            }`}>
            {name}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {editing ? (
        <textarea
          ref={areaRef}
          value={local}
          onChange={handle}
          onBlur={leaveEdit}
          autoFocus
          className="flex-1 bg-transparent text-white/90 placeholder-white/20 p-6 text-sm leading-relaxed outline-none resize-none font-mono custom-scrollbar"
          placeholder={"Escreva suas anotações...\n\nUse [[Nome da Nota]] para linkar outras notas."}
          style={{ caretColor: '#34d399' }}
        />
      ) : (
        <div
          onClick={enterEdit}
          className={`flex-1 overflow-y-auto custom-scrollbar p-6 text-sm leading-relaxed text-white/90 whitespace-pre-wrap font-mono ${readOnly ? 'cursor-default' : 'cursor-text'}`}
        >
          {renderContent(local)}
        </div>
      )}
    </div>
  );
}
