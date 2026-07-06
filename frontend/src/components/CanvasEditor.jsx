import React, { useState, useEffect, useRef } from 'react';
import { NODE_COLORS } from '../constants.jsx';

export default function CanvasEditor({ noteId, data, allNotes, onChange, onOpenNote }) {
  const [nodes, setNodes]           = useState(() => data?.nodes || []);
  const [edges, setEdges]           = useState(() => data?.edges || []);
  const [pan, setPan]               = useState({ x: 100, y: 60 });
  const [zoom, setZoom]             = useState(1);
  const [selected, setSelected]     = useState(null);
  const [connecting, setConnecting] = useState(null);
  const [editingId, setEditingId]   = useState(null);
  const [linkVal, setLinkVal]       = useState('');

  const containerRef = useRef(null);
  const nodesRef     = useRef(nodes);
  const edgesRef     = useRef(edges);
  const saveTimer    = useRef(null);
  const panStart     = useRef(null);
  const panning      = useRef(false);
  const editTextRef  = useRef('');

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

  const onBgDown = (e) => {
    if (e.button !== 0) return;
    if (editingId) { finishEdit(editingId); return; }
    setSelected(null);
    if (connecting) { setConnecting(null); return; }
    panning.current = true;
    panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };
  const onBgMove = (e) => { if (panning.current) setPan({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y }); };
  const onBgUp   = ()  => { panning.current = false; };
  const onWheel  = (e) => { e.preventDefault(); setZoom(z => Math.max(0.15, Math.min(4, z * (e.deltaY < 0 ? 1.12 : 0.9)))); };
  const onBgDbl  = (e) => {
    const pos = toCanvas(e.clientX, e.clientY);
    const id = genId();
    const n = { id, x: pos.x - 55, y: pos.y - 22, text: '', color: 'blue' };
    const nxt = [...nodesRef.current, n]; setNodes(nxt); nodesRef.current = nxt; doSave();
    startEdit(n);
  };

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

  const startResize = (e, node, dir) => {
    e.stopPropagation();
    const el = e.currentTarget.parentElement;
    const rect = el.getBoundingClientRect();
    const startX = e.clientX, startY = e.clientY;
    const startW = node.w || (rect.width / zoom);
    const startH = node.h || (rect.height / zoom);
    const mv = (ev) => {
      const dx = (ev.clientX - startX) / zoom, dy = (ev.clientY - startY) / zoom;
      const upd = {};
      if (dir === 'e' || dir === 'se') upd.w = Math.round(Math.max(80, Math.min(520, startW + dx)));
      if (dir === 's' || dir === 'se') upd.h = Math.round(Math.max(36, Math.min(520, startH + dy)));
      setNodes(prev => { const nxt = prev.map(n => n.id === node.id ? { ...n, ...upd } : n); nodesRef.current = nxt; return nxt; });
    };
    const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); doSave(); };
    document.addEventListener('mousemove', mv);
    document.addEventListener('mouseup', up);
  };

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

  const getMidHandle = (f, t, bend) => {
    const bx = bend?.x || 0, by = bend?.y || 0;
    const fx = f.x + (f.w || 120) / 2, fy = f.y + 24;
    const tx = t.x + (t.w || 120) / 2, ty = t.y + 24;
    return { x: (fx + tx) / 2 + bx * 0.75, y: (fy + ty) / 2 + by * 0.75 };
  };

  const startBendDrag = (e, edge) => {
    e.stopPropagation();
    const startX = e.clientX, startY = e.clientY;
    const origBend = { x: edge.bend?.x || 0, y: edge.bend?.y || 0 };
    const mv = (ev) => {
      const dx = (ev.clientX - startX) / zoom, dy = (ev.clientY - startY) / zoom;
      const newBend = { x: origBend.x + dx * (4 / 3), y: origBend.y + dy * (4 / 3) };
      setEdges(prev => { const nxt = prev.map(ed => ed.id === edge.id ? { ...ed, bend: newBend } : ed); edgesRef.current = nxt; return nxt; });
    };
    const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); doSave(); };
    document.addEventListener('mousemove', mv);
    document.addEventListener('mouseup', up);
  };

  const getPath = (fromId, toId, bend) => {
    const f = nodes.find(n => n.id === fromId), t = nodes.find(n => n.id === toId);
    if (!f || !t) return null;
    const fw = f.w || 120, tw = t.w || 120;
    const fx = f.x + fw / 2, fy = f.y + 24, tx = t.x + tw / 2, ty = t.y + 24;
    const dx = tx - fx, bx = bend?.x || 0, by = bend?.y || 0;
    return `M ${fx} ${fy} C ${fx + dx * 0.5 + bx} ${fy + by}, ${tx - dx * 0.5 + bx} ${ty + by}, ${tx} ${ty}`;
  };

  const selNode = selected?.type === 'node' ? nodes.find(n => n.id === selected.id) : null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="shrink-0 flex items-center gap-1.5 px-3 py-2 border-b border-white/5 bg-black/10 flex-wrap">
        <button onClick={addNode} className="text-xs font-bold px-2.5 py-1 rounded-lg bg-white/10 text-white hover:bg-white/20 transition-colors">+ Balão</button>
        {allNotes.length > 0 && (
          <select value={linkVal} onChange={e => { const n = allNotes.find(x => x.id === e.target.value); addNoteLink(n); setLinkVal(''); }}
            className="text-xs font-bold px-2 py-1 rounded-lg outline-none cursor-pointer"
            style={{ background: '#1e293b', color: '#e2e8f0', border: '1px solid rgba(255,255,255,0.15)' }}>
            <option value="" style={{ background: '#1e293b', color: '#e2e8f0' }}>+ Link de Nota</option>
            {allNotes.map(n => <option key={n.id} value={n.id} style={{ background: '#1e293b', color: '#e2e8f0' }}>{n.titulo || 'Sem título'}</option>)}
          </select>
        )}
        {selNode && (<>
          <div className="w-px h-4 bg-white/10 mx-0.5"/>
          {Object.entries(NODE_COLORS).map(([k, c]) => (
            <button key={k} onClick={() => changeColor(k)} style={{ backgroundColor: c.bg, border: `2px solid ${c.border}` }}
              className={`w-5 h-5 rounded-full transition-transform ${selNode.color === k ? 'scale-125 shadow-md' : 'hover:scale-110'}`}/>
          ))}
          <div className="w-px h-4 bg-white/10 mx-0.5"/>
          <button onClick={deleteSelected} className="text-xs font-bold px-2.5 py-1 rounded-lg bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors">✕ Deletar</button>
        </>)}
        {selected?.type === 'edge' && (
          <button onClick={deleteSelected} className="text-xs font-bold px-2.5 py-1 rounded-lg bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors">✕ Deletar ligação</button>
        )}
        {connecting && <span className="text-emerald-300 text-[11px] font-bold animate-pulse ml-2">Clique em outro balão para conectar · ESC cancela</span>}
        <span className="text-white/18 text-[10px] font-mono ml-auto hidden md:block">2× clique = balão · scroll = zoom · Del = apagar</span>
      </div>

      <div ref={containerRef} className="flex-1 relative overflow-hidden select-none"
        style={{ backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.09) 1.5px, transparent 1.5px)', backgroundSize: `${24 * zoom}px ${24 * zoom}px`, backgroundPosition: `${pan.x}px ${pan.y}px`, backgroundColor: 'rgba(0,0,0,0.15)', cursor: connecting ? 'crosshair' : 'default' }}
        onMouseDown={onBgDown} onMouseMove={onBgMove} onMouseUp={onBgUp} onMouseLeave={onBgUp} onWheel={onWheel} onDoubleClick={onBgDbl}>
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none gap-2">
            <p className="text-white/12 font-black text-2xl">Mapa vazio</p>
            <p className="text-white/10 text-xs">Clique em "+ Balão" ou dê duplo clique na tela</p>
          </div>
        )}
        <div style={{ transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`, transformOrigin: '0 0', position: 'absolute', left: 0, top: 0, width: 4000, height: 4000 }}>
          <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, overflow: 'visible', pointerEvents: 'none' }}>
            <defs>
              <marker id="arrN" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><path d="M0 0 L10 3.5 L0 7z" fill="rgba(255,255,255,0.7)"/></marker>
              <marker id="arrS" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><path d="M0 0 L10 3.5 L0 7z" fill="#60a5fa"/></marker>
            </defs>
            {edges.map(edge => {
              const d = getPath(edge.from, edge.to, edge.bend);
              if (!d) return null;
              const isSel = selected?.type === 'edge' && selected.id === edge.id;
              return (
                <g key={edge.id} style={{ pointerEvents: 'all' }} onMouseDown={e => { e.stopPropagation(); setSelected({ type: 'edge', id: edge.id }); }}>
                  <path d={d} stroke="transparent" strokeWidth="16" fill="none" style={{ pointerEvents: 'stroke' }}/>
                  <path d={d} stroke={isSel ? '#60a5fa' : 'rgba(255,255,255,0.75)'} strokeWidth={isSel ? 3 : 2.5} fill="none" markerEnd={isSel ? 'url(#arrS)' : 'url(#arrN)'} style={{ pointerEvents: 'none' }}/>
                </g>
              );
            })}
          </svg>
          {edges.map(edge => {
            const f = nodes.find(n => n.id === edge.from), t = nodes.find(n => n.id === edge.to);
            if (!f || !t) return null;
            const mid = getMidHandle(f, t, edge.bend);
            const isSel = selected?.type === 'edge' && selected.id === edge.id;
            return (
              <div key={`bh-${edge.id}`} style={{ position: 'absolute', left: mid.x - 8, top: mid.y - 8, width: 16, height: 16, borderRadius: '50%', background: isSel ? '#60a5fa' : 'rgba(255,255,255,0.55)', border: `2px solid ${isSel ? 'white' : 'rgba(255,255,255,0.9)'}`, cursor: 'grab', zIndex: 5, boxShadow: '0 1px 4px rgba(0,0,0,0.4)' }}
                onMouseDown={e => { e.stopPropagation(); startBendDrag(e, edge); }}/>
            );
          })}
          {nodes.map(node => {
            const c = NODE_COLORS[node.color] || NODE_COLORS.blue;
            const isSel = selected?.type === 'node' && selected.id === node.id;
            const isConn = connecting === node.id;
            const isEditing = editingId === node.id;
            const nodeW = node.w, nodeH = node.h;
            const nodeFontSize = Math.max(10, Math.min(32, Math.round(13 * (nodeW || 120) / 120)));
            return (
              <div key={node.id}
                style={{ position: 'absolute', left: node.x, top: node.y, minWidth: nodeW || 80, maxWidth: nodeW || 320, height: nodeH || undefined, minHeight: 36, overflow: nodeH ? 'hidden' : 'visible', backgroundColor: c.bg, border: `2px solid ${isSel ? '#60a5fa' : isConn ? '#10b981' : c.border}`, borderRadius: 12, padding: '8px 12px', boxShadow: isSel ? '0 0 0 3px rgba(96,165,250,0.28), 0 4px 14px rgba(0,0,0,0.22)' : '0 2px 8px rgba(0,0,0,0.18)', cursor: connecting ? 'crosshair' : 'grab', display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', transition: 'border-color 0.1s, box-shadow 0.1s', boxSizing: 'border-box' }}
                onMouseDown={e => onNodeDown(e, node)} onDoubleClick={e => onNodeDbl(e, node)}>
                {node.linkedNoteId && <span style={{ fontSize: 10, marginBottom: 2, opacity: 0.65 }}>🔗</span>}
                {isEditing ? (
                  <div ref={editDivRef} contentEditable suppressContentEditableWarning
                    onInput={e => { editTextRef.current = e.currentTarget.textContent || ''; }}
                    onBlur={() => finishEdit(node.id)}
                    onKeyDown={e => { e.stopPropagation(); if (e.key === 'Escape') { e.preventDefault(); finishEdit(node.id); } }}
                    onClick={e => e.stopPropagation()}
                    style={{ minWidth: 40, maxWidth: nodeW ? nodeW - 24 : 276, outline: 'none', fontSize: nodeFontSize, fontWeight: 700, color: c.text, textAlign: 'center', lineHeight: 1.5, wordBreak: 'break-word', whiteSpace: 'pre-wrap', cursor: 'text' }}/>
                ) : (
                  <span style={{ fontSize: nodeFontSize, fontWeight: 700, color: c.text, textAlign: 'center', lineHeight: 1.5, wordBreak: 'break-word', whiteSpace: 'pre-wrap', display: 'block', maxWidth: nodeW ? nodeW - 24 : 276 }}>
                    {node.text || <em style={{ opacity: 0.32, fontSize: nodeFontSize * 0.85, fontStyle: 'normal' }}>duplo clique</em>}
                  </span>
                )}
                {isSel && !isEditing && !connecting && (
                  <div style={{ position: 'absolute', right: -20, top: '50%', transform: 'translateY(-50%)', width: 20, height: 20, borderRadius: '50%', background: '#10b981', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', fontSize: 13, fontWeight: 900, boxShadow: '0 2px 6px rgba(0,0,0,0.3)', zIndex: 10 }}
                    onMouseDown={e => { e.stopPropagation(); setConnecting(node.id); }} title="Conectar a outro balão">→</div>
                )}
                {isSel && !isEditing && (<>
                  <div style={{ position: 'absolute', right: -5, top: '50%', transform: 'translateY(-50%)', width: 9, height: 30, borderRadius: 5, background: '#60a5fa', cursor: 'e-resize', boxShadow: '0 1px 4px rgba(0,0,0,0.35)', opacity: 0.9 }} onMouseDown={e => startResize(e, node, 'e')} title="Largura"/>
                  <div style={{ position: 'absolute', bottom: -5, left: '50%', transform: 'translateX(-50%)', width: 30, height: 9, borderRadius: 5, background: '#60a5fa', cursor: 's-resize', boxShadow: '0 1px 4px rgba(0,0,0,0.35)', opacity: 0.9 }} onMouseDown={e => startResize(e, node, 's')} title="Altura"/>
                  <div style={{ position: 'absolute', right: -5, bottom: -5, width: 13, height: 13, borderRadius: '2px 6px 6px 6px', background: '#93c5fd', cursor: 'se-resize', boxShadow: '0 1px 4px rgba(0,0,0,0.4)' }} onMouseDown={e => startResize(e, node, 'se')} title="Largura e altura"/>
                  {(nodeW || nodeH) && <div style={{ position: 'absolute', bottom: -20, right: 0, fontSize: 9, color: 'rgba(255,255,255,0.45)', fontFamily: 'monospace', pointerEvents: 'none', whiteSpace: 'nowrap' }}>{nodeW || '…'}×{nodeH || '…'}</div>}
                </>)}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
