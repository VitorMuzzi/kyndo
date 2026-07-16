import React, { useState, useEffect, useRef } from 'react';
import { X, Share2 } from 'lucide-react';
import { API, authFetch } from '../api.js';
import TextEditor from './TextEditor.jsx';
import CanvasEditor from './CanvasEditor.jsx';
import ShareControls from './ShareControls.jsx';

export default function NotasView({ user, allUsers, cards, openItemId, onOpenItemHandled }) {
  const [notes, setNotes]           = useState([]);
  const [activeId, setActiveId]     = useState(null);
  const [search, setSearch]         = useState('');
  const [loading, setLoading]       = useState(true);
  const [saveStatus, setSaveStatus] = useState('idle');
  const saveTimer = useRef(null);

  // Fetch + pick the initial active note in one step: if we were told to open a
  // specific note (openItemId, from a "linked item" click elsewhere), honor that;
  // otherwise fall back to the most recent one. Doing this in a single effect
  // avoids a race with a separate "correct the selection" effect, which could
  // otherwise fire twice (e.g. React StrictMode) and stomp the correction back
  // to the default note.
  useEffect(() => {
    authFetch(`${API}/notes`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setNotes(data);
        setLoading(false);
        if (openItemId && data.some(n => n.id === openItemId)) {
          setActiveId(openItemId);
          onOpenItemHandled?.();
        } else if (data.length > 0) {
          setActiveId(data[0].id);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the mount-time openItemId matters here
  }, []);

  // If openItemId changes while already mounted (e.g. clicking a different
  // linked note without leaving the Notas view), jump to it.
  useEffect(() => {
    if (!openItemId || loading) return;
    if (notes.some(n => n.id === openItemId)) {
      setActiveId(openItemId);
      onOpenItemHandled?.();
    }
  }, [openItemId]);

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
      <aside className="w-56 shrink-0 flex flex-col bg-black/40 backdrop-blur-sm border-r border-white/10">
        <div className="p-3 border-b border-white/10 shrink-0">
          <p className="text-white/50 font-black text-[10px] uppercase tracking-widest mb-2">Notas · {user.nome}</p>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar..." autoComplete="off"
            className="w-full bg-white/10 hover:bg-white/15 text-white placeholder-white/25 text-xs px-3 py-1.5 rounded-lg outline-none focus:bg-white/20 transition-colors"/>
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
                <p className={`text-xs font-bold truncate flex items-center gap-1 ${activeId === note.id ? 'text-white' : 'text-white/60'}`}>
                  {note.titulo || 'Sem título'}
                  {note.owner === false && <Share2 size={10} className="text-emerald-300/70 shrink-0" title="Compartilhada com você"/>}
                </p>
                <p className="text-[10px] text-white/22 mt-0.5">{note.tipo === 'canvas' ? '🗺 Mapa' : '📝 Texto'} · {note.criado_em}</p>
              </div>
              {note.owner !== false && (
                <button onClick={e => deleteNote(note.id, e)} className="opacity-0 group-hover:opacity-100 text-white/25 hover:text-red-400 transition-all shrink-0 p-0.5 mt-0.5"><X size={11}/></button>
              )}
            </div>
          ))}
        </div>
        <div className="p-3 border-t border-white/10 shrink-0 flex gap-2">
          <button onClick={() => createNote('texto')}  className="flex-1 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-bold rounded-lg transition-colors">+ Texto</button>
          <button onClick={() => createNote('canvas')} className="flex-1 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-bold rounded-lg transition-colors">+ Mapa</button>
        </div>
      </aside>

      {activeNote ? (
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-b border-white/10 bg-black/20">
            <input value={activeNote.titulo || ''} onChange={e => updateNote({ titulo: e.target.value })}
              disabled={activeNote.pode_editar === false}
              className="flex-1 bg-transparent text-white font-black text-lg outline-none placeholder-white/25 min-w-0 disabled:opacity-60" placeholder="Sem título"/>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full transition-all shrink-0 ${saveStatus === 'saving' ? 'bg-yellow-400/20 text-yellow-300' : saveStatus === 'saved' ? 'bg-emerald-400/20 text-emerald-300' : 'opacity-0'}`}>
              {saveStatus === 'saving' ? 'Salvando...' : 'Salvo ✓'}
            </span>
          </div>
          <ShareControls item={activeNote} allUsers={allUsers} allCards={cards} isOwner={activeNote.owner !== false} currentUserId={user.id}
            onChange={changes => updateNote(changes)}/>
          {activeNote.tipo === 'canvas' ? (
            <CanvasEditor key={activeNote.id} noteId={activeNote.id} data={activeNote.canvas_data || { nodes: [], edges: [] }} allNotes={notes} onChange={canvas_data => updateNote({ canvas_data })} onOpenNote={setActiveId} readOnly={activeNote.pode_editar === false}/>
          ) : (
            <TextEditor key={activeNote.id} noteId={activeNote.id} conteudo={activeNote.conteudo || ''} allNotes={notes} onChange={conteudo => updateNote({ conteudo })} onOpenNote={setActiveId} readOnly={activeNote.pode_editar === false}/>
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
