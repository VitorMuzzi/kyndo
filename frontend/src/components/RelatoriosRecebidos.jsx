import React, { useEffect, useState } from 'react';
import { ArrowLeft, Inbox, MessageSquare } from 'lucide-react';
import { API, authFetch } from '../api.js';
import { formatarData, userColor } from '../constants.jsx';
import ConversaRelatorio from './ConversaRelatorio.jsx';

const dataHora = (iso) => (iso ? new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');
const ORIGEM = { agendado: 'envio agendado', automatico: 'envio automático' };

// Aba "Recebidos" dos Relatórios: o que mandaram para quem está olhando
// (gestor). Abrir um relatório marca como lido; a resposta vai para quem escreveu.
export default function RelatoriosRecebidos({ user, abrir, onLido }) {
  const [lista, setLista] = useState(null);
  const [sel, setSel] = useState(abrir ? { autor_id: abrir.autor_id, data: abrir.data } : null);
  const [detalhe, setDetalhe] = useState(null);

  const carregarLista = () => authFetch(`${API}/relatorios/recebidos`).then(r => (r.ok ? r.json() : [])).then(setLista);

  useEffect(() => {
    carregarLista();
    const t = setInterval(carregarLista, 30000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!sel) { setDetalhe(null); return; }
    let vivo = true;
    const buscar = () => authFetch(`${API}/relatorios/recebidos/${sel.autor_id}/${sel.data}`)
      .then(r => (r.ok ? r.json() : null)).then(d => {
        if (!vivo) return;
        setDetalhe(d);
        carregarLista();
        onLido();
      });
    setDetalhe(null);
    buscar();
    const t = setInterval(buscar, 30000);
    return () => { vivo = false; clearInterval(t); };
  }, [sel?.autor_id, sel?.data]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 items-start">
      <section className={`lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-3 ${sel ? 'hidden lg:block' : ''}`}>
        <h2 className="flex items-center gap-2 px-2 pb-2 text-base font-black text-white"><Inbox size={16} className="text-slate-400"/> Recebidos</h2>
        {lista === null ? <p className="px-2 text-sm text-slate-500">Carregando…</p>
          : lista.length === 0 ? <p className="px-2 pb-2 text-sm text-slate-500">Ninguém enviou relatório para você ainda.</p> : (
          <ul className="space-y-0.5 max-h-[70dvh] overflow-y-auto custom-scrollbar">
            {lista.map(r => {
              const ativo = sel?.autor_id === r.autor_id && sel?.data === r.data;
              const novo = !r.lido || r.mensagens_nao_lidas > 0;
              return (
                <li key={`${r.autor_id}-${r.data}`}>
                  <button onClick={() => setSel({ autor_id: r.autor_id, data: r.data })}
                    className={`w-full text-left px-2 py-2 rounded-lg transition-colors ${ativo ? 'bg-emerald-500/10' : 'hover:bg-white/5'}`}>
                    <div className="flex items-center gap-2">
                      {novo && <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" title={!r.lido ? 'Não lido' : 'Resposta nova'}/>}
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${userColor(r.autor_nome)}`}>{r.autor_nome}</span>
                      <span className={`text-xs ${novo ? 'font-black text-white' : 'font-bold text-slate-300'}`}>{formatarData(r.data)}</span>
                      {r.mensagens_nao_lidas > 0 && (
                        <span className="ml-auto flex items-center gap-1 text-[10px] font-bold text-emerald-300"><MessageSquare size={11}/> {r.mensagens_nao_lidas}</span>
                      )}
                    </div>
                    <span className="block mt-0.5 text-[11px] text-slate-500 truncate">{r.resumo}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className={`lg:col-span-3 bg-slate-900 border border-slate-800 rounded-2xl p-4 md:p-5 space-y-4 ${sel ? '' : 'hidden lg:block'}`}>
        {!sel ? <p className="text-sm text-slate-500">Escolha um relatório na lista.</p>
          : !detalhe ? <p className="text-sm text-slate-500">Carregando…</p> : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={() => setSel(null)} className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5" title="Voltar"><ArrowLeft size={16}/></button>
              <h2 className="text-base font-black text-white">Relatório de {detalhe.autor_nome} — {formatarData(detalhe.data)}</h2>
              <span className="text-[11px] text-slate-500">
                recebido em {dataHora(detalhe.enviado_em)}{ORIGEM[detalhe.origem] ? ` (${ORIGEM[detalhe.origem]})` : ''}
                {detalhe.envios > 1 ? ` · enviado ${detalhe.envios} vezes, esta é a última versão` : ''}
              </span>
            </div>
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-100 leading-relaxed whitespace-pre-wrap break-words">{detalhe.conteudo}</div>
            <div className="pt-3 border-t border-slate-800 space-y-2">
              <h3 className="text-xs font-bold text-slate-400 uppercase">Conversa com {detalhe.autor_nome}</h3>
              <ConversaRelatorio autorId={detalhe.autor_id} data={detalhe.data} gestorId={user.id} mensagens={detalhe.mensagens}
                onMensagens={m => setDetalhe(d => ({ ...d, mensagens: m }))}
                vazio={`Escreva aqui para responder — ${detalhe.autor_nome} vê a resposta no Kyndo e recebe um aviso por e-mail.`}/>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
