import React, { useState, useEffect, useRef } from 'react';
import { X, Share2 } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { DRAW_W, DRAW_H, DRAW_COLORS, DRAW_SIZES } from '../constants.jsx';
import ShareControls from './ShareControls.jsx';

export default function DesenhoView({ user, allUsers, cards, openItemId, onOpenItemHandled }) {
  const [drawings, setDrawings]     = useState([]);
  const [activeId, setActiveId]     = useState(null);
  const [search, setSearch]         = useState('');
  const [loading, setLoading]       = useState(true);
  const [saveStatus, setSaveStatus] = useState('idle');
  const canvasRef  = useRef(null);
  const saveTimer  = useRef(null);
  const isDrawing  = useRef(false);
  const [tool, setTool]           = useState('pen');
  const [color, setColor]         = useState('#ffffff');
  const [size, setSize]           = useState(5);
  const [undoStack, setUndoStack] = useState([]);

  // Fetch + pick the initial active drawing in one step (see NotasView.jsx for
  // why this can't be split into a separate "correct the selection" effect).
  useEffect(() => {
    authFetch(`${API}/drawings`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setDrawings(data);
        setLoading(false);
        if (openItemId && data.some(d => d.id === openItemId)) {
          setActiveId(openItemId);
          onOpenItemHandled?.();
        } else if (data.length > 0) {
          setActiveId(data[0].id);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the mount-time openItemId matters here
  }, []);

  // If openItemId changes while already mounted, jump to it.
  useEffect(() => {
    if (!openItemId || loading) return;
    if (drawings.some(d => d.id === openItemId)) {
      setActiveId(openItemId);
      onOpenItemHandled?.();
    }
  }, [openItemId]);

  const activeDrawing = drawings.find(d => d.id === activeId) || null;
  const readOnly = activeDrawing ? activeDrawing.pode_editar === false : false;

  // Load the active drawing's saved image onto the canvas whenever it changes
  useEffect(() => {
    const ctx = canvasRef.current?.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, DRAW_W, DRAW_H);
    setUndoStack([]);
    if (activeDrawing?.data) {
      const img = new Image();
      img.onload = () => ctx.drawImage(img, 0, 0);
      img.src = activeDrawing.data;
    }
  }, [activeId]);

  const createDrawing = () => {
    authFetch(`${API}/drawings`, { method: 'POST', body: JSON.stringify({ titulo: 'Novo desenho', data: '' }) })
      .then(r => r.ok ? r.json() : null).then(d => {
        if (!d) return;
        setDrawings(prev => [d, ...prev]);
        setActiveId(d.id);
      });
  };

  const updateDrawing = (changes) => {
    if (!activeId || !activeDrawing) return;
    const updated = { ...activeDrawing, ...changes };
    setDrawings(prev => prev.map(d => d.id === activeId ? updated : d));
    setSaveStatus('saving');
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      authFetch(`${API}/drawings/${activeId}`, { method: 'PUT', body: JSON.stringify(updated) })
        .then(() => { setSaveStatus('saved'); setTimeout(() => setSaveStatus('idle'), 2000); });
    }, 700);
  };

  const deleteDrawing = (id, e) => {
    e.stopPropagation();
    const remaining = drawings.filter(d => d.id !== id);
    setDrawings(remaining);
    if (activeId === id) setActiveId(remaining[0]?.id || null);
    authFetch(`${API}/drawings/${id}`, { method: 'DELETE' });
  };

  const filtered = drawings.filter(d => d.titulo?.toLowerCase().includes(search.toLowerCase()));

  const getPos = (e) => {
    const c = canvasRef.current;
    const rect = c.getBoundingClientRect();
    return { x: (e.clientX - rect.left) * (DRAW_W / rect.width), y: (e.clientY - rect.top) * (DRAW_H / rect.height) };
  };

  const scheduleSave = () => {
    updateDrawing({ data: canvasRef.current.toDataURL('image/png') });
  };

  const startDraw = (e) => {
    if (readOnly) return;
    e.preventDefault();
    if (!e.isPrimary) return;
    canvasRef.current.setPointerCapture(e.pointerId);
    const ctx = canvasRef.current.getContext('2d');
    setUndoStack(prev => [...prev.slice(-19), canvasRef.current.toDataURL()]);
    const pos = getPos(e);
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
    ctx.globalCompositeOperation = tool === 'eraser' ? 'destination-out' : 'source-over';
    ctx.strokeStyle = tool === 'eraser' ? 'rgba(0,0,0,1)' : color;
    ctx.lineWidth   = tool === 'eraser' ? size * 3 : size;
    ctx.lineCap     = 'round';
    ctx.lineJoin    = 'round';
    isDrawing.current = true;
  };

  const draw = (e) => {
    if (readOnly) return;
    e.preventDefault();
    if (!isDrawing.current || !e.isPrimary) return;
    const ctx = canvasRef.current.getContext('2d');
    const pos = getPos(e);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
  };

  const endDraw = (e) => {
    if (!isDrawing.current) return;
    if (e && !e.isPrimary) return;
    isDrawing.current = false;
    canvasRef.current.getContext('2d').beginPath();
    scheduleSave();
  };

  const undo = () => {
    if (readOnly || !undoStack.length) return;
    const prev = undoStack[undoStack.length - 1];
    const ctx = canvasRef.current.getContext('2d');
    ctx.clearRect(0, 0, DRAW_W, DRAW_H);
    if (prev) { const img = new Image(); img.onload = () => { ctx.drawImage(img, 0, 0); scheduleSave(); }; img.src = prev; }
    setUndoStack(s => s.slice(0, -1));
  };

  const clearCanvas = () => {
    if (readOnly) return;
    setUndoStack(prev => [...prev.slice(-19), canvasRef.current.toDataURL()]);
    canvasRef.current.getContext('2d').clearRect(0, 0, DRAW_W, DRAW_H);
    scheduleSave();
  };

  return (
    <div className="absolute inset-0 flex overflow-hidden">
      <aside className="w-56 shrink-0 flex flex-col bg-black/40 backdrop-blur-sm border-r border-white/10">
        <div className="p-3 border-b border-white/10 shrink-0">
          <p className="text-white/50 font-black text-[10px] uppercase tracking-widest mb-2">Desenhos · {user.nome}</p>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar..." autoComplete="off"
            className="w-full bg-white/10 hover:bg-white/15 text-white placeholder-white/25 text-xs px-3 py-1.5 rounded-lg outline-none focus:bg-white/20 transition-colors"/>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar py-1 min-h-0">
          {loading ? (
            <p className="text-white/20 text-xs text-center py-6">Carregando...</p>
          ) : filtered.length === 0 ? (
            <p className="text-white/15 text-xs text-center py-6 font-bold">{search ? 'Nenhum resultado' : 'Nenhum desenho'}</p>
          ) : filtered.map(d => (
            <div key={d.id} onClick={() => setActiveId(d.id)}
              className={`px-3 py-2.5 cursor-pointer group flex items-start justify-between gap-1 transition-colors ${activeId === d.id ? 'bg-white/15' : 'hover:bg-white/8'}`}>
              <div className="min-w-0 flex-1">
                <p className={`text-xs font-bold truncate flex items-center gap-1 ${activeId === d.id ? 'text-white' : 'text-white/60'}`}>
                  {d.titulo || 'Sem título'}
                  {d.owner === false && <Share2 size={10} className="text-emerald-300/70 shrink-0" title="Compartilhado com você"/>}
                </p>
                <p className="text-[10px] text-white/22 mt-0.5">🎨 Desenho · {d.criado_em}</p>
              </div>
              {d.owner !== false && (
                <button onClick={e => deleteDrawing(d.id, e)} className="opacity-0 group-hover:opacity-100 text-white/25 hover:text-red-400 transition-all shrink-0 p-0.5 mt-0.5"><X size={11}/></button>
              )}
            </div>
          ))}
        </div>
        <div className="p-3 border-t border-white/10 shrink-0">
          <button onClick={createDrawing} className="w-full py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-bold rounded-lg transition-colors">+ Novo desenho</button>
        </div>
      </aside>

      {activeDrawing ? (
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <div className="shrink-0 flex items-center gap-3 px-5 py-3 border-b border-white/10 bg-black/20">
            <input value={activeDrawing.titulo || ''} onChange={e => updateDrawing({ titulo: e.target.value })}
              disabled={readOnly}
              className="flex-1 bg-transparent text-white font-black text-lg outline-none placeholder-white/25 min-w-0 disabled:opacity-60" placeholder="Sem título"/>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full transition-all shrink-0 ${saveStatus === 'saving' ? 'bg-yellow-400/20 text-yellow-300' : saveStatus === 'saved' ? 'bg-emerald-400/20 text-emerald-300' : 'opacity-0'}`}>
              {saveStatus === 'saving' ? 'Salvando...' : 'Salvo ✓'}
            </span>
          </div>
          <ShareControls item={activeDrawing} allUsers={allUsers} allCards={cards} isOwner={activeDrawing.owner !== false} currentUserId={user.id}
            onChange={changes => updateDrawing(changes)}/>

          <div className="shrink-0 flex items-center gap-2 px-4 py-2 border-b border-white/10 bg-black/25 flex-wrap">
            {readOnly ? (
              <span className="text-white/25 text-[11px] font-bold uppercase tracking-widest">Somente leitura</span>
            ) : (<>
              <button onClick={() => setTool('pen')} className={`text-xs font-bold px-3 py-1.5 rounded-lg transition-colors ${tool === 'pen' ? 'bg-white/20 text-white' : 'text-white/40 hover:text-white/60'}`}>✏ Lápis</button>
              <button onClick={() => setTool('eraser')} className={`text-xs font-bold px-3 py-1.5 rounded-lg transition-colors ${tool === 'eraser' ? 'bg-white/20 text-white' : 'text-white/40 hover:text-white/60'}`}>⬜ Borracha</button>
              <div className="w-px h-4 bg-white/10 mx-0.5"/>
              <div className="flex items-center gap-1.5">
                {DRAW_COLORS.map(c => (
                  <button key={c} onClick={() => { setColor(c); setTool('pen'); }}
                    style={{ width: 20, height: 20, borderRadius: '50%', backgroundColor: c, flexShrink: 0, border: `2px solid ${color === c && tool === 'pen' ? '#60a5fa' : 'rgba(255,255,255,0.2)'}`, transform: color === c && tool === 'pen' ? 'scale(1.3)' : 'scale(1)', transition: 'transform 0.1s' }}/>
                ))}
              </div>
              <div className="w-px h-4 bg-white/10 mx-0.5"/>
              <div className="flex items-center gap-2">
                {DRAW_SIZES.map(s => (
                  <button key={s} onClick={() => setSize(s)}
                    style={{ width: Math.min(s + 10, 30), height: Math.min(s + 10, 30), borderRadius: '50%', flexShrink: 0, backgroundColor: tool === 'eraser' ? '#94a3b8' : color, border: `2px solid ${size === s ? '#60a5fa' : 'rgba(255,255,255,0.2)'}`, transform: size === s ? 'scale(1.2)' : 'scale(1)', transition: 'transform 0.1s' }}/>
                ))}
              </div>
              <div className="w-px h-4 bg-white/10 mx-0.5"/>
              <button onClick={undo} disabled={!undoStack.length} className={`text-xs font-bold px-3 py-1.5 rounded-lg transition-colors ${undoStack.length ? 'text-white/60 hover:text-white hover:bg-white/10' : 'text-white/20 cursor-not-allowed'}`}>↩ Desfazer</button>
              <button onClick={clearCanvas} className="text-xs font-bold px-3 py-1.5 rounded-lg text-red-300/60 hover:text-red-300 hover:bg-red-500/10 transition-colors">🗑 Limpar</button>
            </>)}
          </div>
          <div className="flex-1 relative overflow-hidden" style={{ background: '#0f172a' }}>
            <canvas ref={canvasRef} width={DRAW_W} height={DRAW_H}
              style={{ width: '100%', height: '100%', display: 'block', cursor: readOnly ? 'default' : (tool === 'eraser' ? 'cell' : 'crosshair'), touchAction: 'none' }}
              onPointerDown={startDraw} onPointerMove={draw} onPointerUp={endDraw} onPointerCancel={endDraw} onPointerLeave={endDraw}/>
          </div>
        </div>
      ) : !loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-white/18 font-black text-xl mb-4">Nenhum desenho ainda</p>
            <button onClick={createDrawing} className="px-5 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-bold rounded-xl transition-colors">+ Novo desenho</button>
          </div>
        </div>
      )}
    </div>
  );
}
