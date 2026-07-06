import React, { useState, useRef, useEffect } from 'react';
import { API, authFetch } from '../api.js';
import { DRAW_W, DRAW_H, DRAW_COLORS, DRAW_SIZES } from '../constants.jsx';

export default function DesenhoView() {
  const canvasRef = useRef(null);
  const [tool, setTool]           = useState('pen');
  const [color, setColor]         = useState('#ffffff');
  const [size, setSize]           = useState(5);
  const [undoStack, setUndoStack] = useState([]);
  const [saveStatus, setSaveStatus] = useState('idle');
  const isDrawing = useRef(false);
  const saveTimer = useRef(null);

  useEffect(() => {
    authFetch(`${API}/drawing/me`).then(r => r.ok ? r.json() : null).then(d => {
      if (d?.data && canvasRef.current) {
        const img = new Image();
        img.onload = () => canvasRef.current.getContext('2d').drawImage(img, 0, 0);
        img.src = d.data;
      }
    });
  }, []);

  const getPos = (e) => {
    const c = canvasRef.current;
    const rect = c.getBoundingClientRect();
    return { x: (e.clientX - rect.left) * (DRAW_W / rect.width), y: (e.clientY - rect.top) * (DRAW_H / rect.height) };
  };

  const scheduleSave = () => {
    setSaveStatus('saving');
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      const data = canvasRef.current.toDataURL('image/png');
      authFetch(`${API}/drawing/me`, { method: 'PUT', body: JSON.stringify({ data }) })
        .then(() => { setSaveStatus('saved'); setTimeout(() => setSaveStatus('idle'), 2000); });
    }, 2000);
  };

  const startDraw = (e) => {
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
    if (!undoStack.length) return;
    const prev = undoStack[undoStack.length - 1];
    const ctx = canvasRef.current.getContext('2d');
    ctx.clearRect(0, 0, DRAW_W, DRAW_H);
    if (prev) { const img = new Image(); img.onload = () => { ctx.drawImage(img, 0, 0); scheduleSave(); }; img.src = prev; }
    setUndoStack(s => s.slice(0, -1));
  };

  const clearCanvas = () => {
    setUndoStack(prev => [...prev.slice(-19), canvasRef.current.toDataURL()]);
    canvasRef.current.getContext('2d').clearRect(0, 0, DRAW_W, DRAW_H);
    scheduleSave();
  };

  return (
    <div className="absolute inset-0 flex flex-col overflow-hidden">
      <div className="shrink-0 flex items-center gap-2 px-4 py-2 border-b border-white/10 bg-black/25 flex-wrap">
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
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ml-auto transition-opacity duration-300 ${saveStatus === 'idle' ? 'opacity-0' : 'opacity-100'} ${saveStatus === 'saving' ? 'bg-yellow-400/20 text-yellow-300' : 'bg-emerald-400/20 text-emerald-300'}`}>
          {saveStatus === 'saving' ? 'Salvando...' : 'Salvo ✓'}
        </span>
      </div>
      <div className="flex-1 relative overflow-hidden" style={{ background: '#0f172a' }}>
        <canvas ref={canvasRef} width={DRAW_W} height={DRAW_H}
          style={{ width: '100%', height: '100%', display: 'block', cursor: tool === 'eraser' ? 'cell' : 'crosshair', touchAction: 'none' }}
          onPointerDown={startDraw} onPointerMove={draw} onPointerUp={endDraw} onPointerCancel={endDraw} onPointerLeave={endDraw}/>
      </div>
    </div>
  );
}
