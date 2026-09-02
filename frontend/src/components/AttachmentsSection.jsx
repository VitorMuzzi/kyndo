import React, { useEffect, useRef, useState } from 'react';
import { Paperclip, Download, Trash2, FileText } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { userColor } from '../constants.jsx';

const MAX_MB = 20;

function formatarTamanho(bytes) {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AttachmentsSection({ cardId, user, canManage }) {
  const [anexos, setAnexos] = useState([]);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState('');
  const inputRef = useRef(null);

  const recarregar = () => {
    authFetch(`${API}/cards/${cardId}/attachments`).then(r => (r.ok ? r.json() : [])).then(setAnexos);
  };

  useEffect(() => { if (cardId) recarregar(); }, [cardId]);

  const enviarArquivo = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (file.size > MAX_MB * 1024 * 1024) { setErro(`Arquivo maior que ${MAX_MB}MB.`); return; }
    setErro('');
    setEnviando(true);
    const body = new FormData();
    body.append('file', file);
    authFetch(`${API}/cards/${cardId}/attachments`, { method: 'POST', body })
      .then(r => { if (!r.ok) throw new Error(); return r; })
      .then(recarregar)
      .catch(() => setErro('Não foi possível enviar o arquivo.'))
      .finally(() => setEnviando(false));
  };

  const baixar = async (anexo) => {
    const res = await authFetch(`${API}/attachments/${anexo.id}/download`);
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = anexo.nome_original;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  };

  const apagar = (anexo) => {
    if (!window.confirm(`Apagar o anexo "${anexo.nome_original}"?`)) return;
    authFetch(`${API}/attachments/${anexo.id}`, { method: 'DELETE' }).then(recarregar);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-300 font-bold text-sm"><Paperclip size={16}/> Anexos</div>
        <div>
          <input ref={inputRef} type="file" className="hidden" onChange={enviarArquivo}/>
          <button onClick={() => inputRef.current?.click()} disabled={enviando} className="px-2 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-slate-300 rounded-lg text-xs font-bold transition-colors">
            {enviando ? 'Enviando...' : '+ Anexar arquivo'}
          </button>
        </div>
      </div>
      {erro && <p className="text-xs text-red-400">{erro}</p>}
      {anexos.length > 0 && (
        <div className="space-y-1.5">
          {anexos.map(a => (
            <div key={a.id} className="flex items-center gap-2 p-2 bg-slate-800 border border-slate-700 rounded-lg text-sm">
              <FileText size={16} className="text-slate-400 shrink-0"/>
              <div className="min-w-0 flex-1">
                <p className="text-slate-200 font-bold truncate">{a.nome_original}</p>
                <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
                  <span className="text-[10px] text-slate-500">{formatarTamanho(a.tamanho)}</span>
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${userColor(a.enviado_por)}`}>{a.enviado_por}</span>
                </div>
              </div>
              <button onClick={() => baixar(a)} title="Baixar" className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-slate-700 rounded-lg transition-colors shrink-0"><Download size={14}/></button>
              {(canManage || a.enviado_por === user.nome) && (
                <button onClick={() => apagar(a)} title="Apagar" className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-700 rounded-lg transition-colors shrink-0"><Trash2 size={14}/></button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
