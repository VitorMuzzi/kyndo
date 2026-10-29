import React, { useEffect, useState } from 'react';
import { RotateCcw, ScrollText, Search, Trash2 } from 'lucide-react';
import { API, authFetch } from '../api.js';

const ACAO_LABELS = {
  card_criado: 'criou o card',
  card_excluido: 'excluiu o card',
  card_restaurado: 'recuperou o card',
  card_fundido: 'fundiu um card neste',
  fusao_desfeita: 'desfez a fusão',
  titulo_alterado: 'alterou o título',
  descricao_alterada: 'alterou a descrição',
  status_alterado: 'moveu o card de coluna',
  prioridade_alterada: 'alterou a prioridade',
  prazo_alterado: 'alterou o prazo',
  github_url_alterado: 'alterou o repositório GitHub',
  responsaveis_alterados: 'alterou os responsáveis',
  etapa_criada: 'criou a etapa',
  etapa_editada: 'editou a etapa',
  etapa_concluida: 'concluiu a etapa',
  etapa_reaberta: 'reabriu a etapa',
  etapa_excluida: 'excluiu a etapa',
  etapa_observacao_editada: 'alterou a observação da etapa',
  etapa_indentada: 'transformou em sub-etapa',
  etapa_desindentada: 'transformou em etapa',
  etapas_reordenadas: 'reordenou as etapas',
  subetapa_criada: 'criou a sub-etapa',
  subetapa_editada: 'editou a sub-etapa',
  subetapa_concluida: 'concluiu a sub-etapa',
  subetapa_reaberta: 'reabriu a sub-etapa',
  subetapa_excluida: 'excluiu a sub-etapa',
  subetapa_movida: 'moveu a sub-etapa',
  comentario_adicionado: 'comentou',
  comentario_removido: 'removeu um comentário',
  sugestao_criada: 'sugeriu uma mudança',
  sugestao_aceita: 'aceitou uma sugestão',
  sugestao_rejeitada: 'recusou uma sugestão',
  sugestao_aceita_sem_aplicar: 'aceitou uma sugestão (alvo não encontrado, nada foi aplicado)',
  sugestao_revogada_sem_reverter: 'revogou uma sugestão sem reverter o campo',
  sugestao_apagada: 'apagou uma sugestão',
  sugestao_restaurada: 'recuperou uma sugestão',
  sugestao_decisao_desfeita: 'desfez a decisão de uma sugestão',
  recorrencia_configurada: 'configurou a recorrência do card',
  recorrencia_desativada: 'desativou a recorrência do card',
  tarefa_recorrente_reiniciada: 'reiniciou automaticamente (tarefa recorrente)',
  reinicio_recorrente_desfeito: 'desfez o reinício automático',
  anexo_adicionado: 'anexou um arquivo',
  anexo_removido: 'removeu um anexo',
  anexo_restaurado: 'recuperou um anexo',
  tempo_apagado: 'apagou um registro de tempo',
  tempo_restaurado: 'recuperou um registro de tempo',
  nota_excluida: 'excluiu a nota',
  nota_restaurada: 'recuperou a nota',
  desenho_excluido: 'excluiu o desenho',
  desenho_restaurado: 'recuperou o desenho',
  usuario_criado: 'criou o usuário',
  usuario_excluido: 'excluiu o usuário',
  usuario_restaurado: 'recuperou o usuário',
  usuario_renomeado: 'renomeou o usuário',
  senha_redefinida: 'definiu uma senha temporária para',
  senha_redefinida_por_email: 'redefiniu a senha pelo link do e-mail:',
  email_alterado: 'alterou o e-mail de',
  config_emails_alterada: 'alterou a configuração dos',
  cargos_do_usuario_alterados: 'alterou os cargos de',
  cargo_criado: 'criou o cargo',
  cargo_alterado: 'alterou o cargo',
  cargo_excluido: 'excluiu o cargo',
  cargo_restaurado: 'recuperou o cargo',
  coluna_criada: 'criou a coluna',
  coluna_alterada: 'alterou a coluna',
  coluna_arquivada: 'arquivou a coluna',
};

const FILTROS = [
  { key: 'tudo', label: 'Tudo' },
  { key: 'exclusoes', label: 'Exclusões' },
];

function formatData(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('pt-BR');
}

export default function AuditLogPanel() {
  const [logs, setLogs] = useState(null);
  const [erro, setErro] = useState('');
  const [filtro, setFiltro] = useState('tudo');
  const [busca, setBusca] = useState('');
  const [recarga, setRecarga] = useState(0);
  const [desfazendo, setDesfazendo] = useState(null);
  const [avisos, setAvisos] = useState({});  // id do registro -> { ok, texto }

  useEffect(() => {
    authFetch(`${API}/audit-log${filtro === 'exclusoes' ? '?somente=exclusoes' : ''}`)
      .then(r => (r.ok ? r.json() : Promise.reject(r)))
      .then(setLogs)
      .catch(() => setErro('Não foi possível carregar o log de auditoria.'));
  }, [filtro, recarga]);

  const desfazer = async (l) => {
    setDesfazendo(l.id);
    try {
      const res = await authFetch(`${API}/audit-log/${l.id}/desfazer`, { method: 'POST' });
      const corpo = await res.json().catch(() => ({}));
      setAvisos(a => ({ ...a, [l.id]: res.ok
        ? { ok: true, texto: corpo.mensagem || 'Desfeito.' }
        : { ok: false, texto: corpo.detail || 'Não foi possível desfazer.' } }));
      if (res.ok) setRecarga(n => n + 1);
    } catch {
      setAvisos(a => ({ ...a, [l.id]: { ok: false, texto: 'Falha de conexão com o servidor.' } }));
    } finally {
      setDesfazendo(null);
    }
  };

  const termo = busca.trim().toLowerCase();
  const visiveis = (logs || []).filter(l => !termo || [l.usuario, l.card_titulo, l.detalhe, ACAO_LABELS[l.acao], l.valor_antigo, l.valor_novo]
    .some(v => (v || '').toLowerCase().includes(termo)));

  return (
    <div>
      <h3 className="text-lg font-bold text-slate-100 mb-1 flex items-center gap-2"><ScrollText size={20}/> Log de Auditoria</h3>
      <p className="text-xs text-slate-500 mb-4">
        Tudo que é excluído fica recuperável por 30 dias. Desfazer só acontece se ninguém mexeu naquilo depois.
      </p>

      <div className="flex items-center gap-2 flex-wrap mb-3">
        <div className="flex items-center bg-slate-800 rounded-lg p-0.5">
          {FILTROS.map(f => (
            <button key={f.key} onClick={() => setFiltro(f.key)}
              className={`px-3 py-1 rounded-md text-xs font-bold transition-colors ${filtro === f.key ? 'bg-slate-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
              {f.key === 'exclusoes' && <Trash2 size={11} className="inline mr-1 -mt-0.5"/>}{f.label}
            </button>
          ))}
        </div>
        <div className="flex-1 min-w-[180px] flex items-center gap-2 bg-slate-800 border border-slate-700 rounded-lg px-2 py-1">
          <Search size={13} className="text-slate-500 shrink-0"/>
          <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar por pessoa, card, texto..."
            className="flex-1 min-w-0 bg-transparent text-xs text-slate-100 outline-none placeholder:text-slate-500"/>
        </div>
      </div>

      {erro && <div className="mb-4 text-sm font-bold text-red-400 bg-red-500/10 p-2 rounded">{erro}</div>}
      {!logs && !erro && <p className="text-sm text-slate-500">Carregando...</p>}
      {logs && visiveis.length === 0 && <p className="text-sm text-slate-500">Nenhum registro encontrado.</p>}
      <div className="space-y-2 max-h-[60vh] overflow-y-auto custom-scrollbar pr-1">
        {visiveis.map(l => {
          const aviso = avisos[l.id];
          const desfeito = !!l.revertido_em;
          return (
            <div key={l.id} className={`p-3 border rounded-xl shadow-sm text-sm ${desfeito ? 'bg-slate-800/50 border-slate-700/50 opacity-70' : l.eh_exclusao ? 'bg-red-500/5 border-red-500/20' : 'bg-slate-800 border-slate-700'}`}>
              <div className="flex justify-between items-start gap-2">
                <p className="text-slate-200 min-w-0">
                  <span className="font-bold text-slate-100">{l.usuario}</span>{' '}
                  {ACAO_LABELS[l.acao] || l.acao}
                  {l.card_titulo && <> {l.card_id ? 'em ' : ''}<span className="font-bold text-slate-100">"{l.card_titulo}"</span></>}
                  {l.detalhe && <> — <span className="italic text-slate-400">{l.detalhe}</span></>}
                </p>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] text-slate-500 font-semibold whitespace-nowrap">{formatData(l.data)}</span>
                  {l.pode_desfazer && (
                    <button onClick={() => desfazer(l)} disabled={desfazendo === l.id}
                      title={l.eh_exclusao ? 'Recuperar o que foi excluído' : 'Desfazer esta alteração'}
                      className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-bold transition-colors disabled:opacity-50 ${l.eh_exclusao ? 'bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/40' : 'bg-slate-700 text-slate-200 hover:bg-slate-600'}`}>
                      <RotateCcw size={11}/> {desfazendo === l.id ? '...' : l.eh_exclusao ? 'Recuperar' : 'Desfazer'}
                    </button>
                  )}
                </div>
              </div>
              {(l.valor_antigo || l.valor_novo) && (
                <p className="mt-1 text-xs text-slate-400 break-words">
                  <span className="line-through">{l.valor_antigo || '(vazio)'}</span>
                  {' → '}
                  <span className="font-bold text-slate-200">{l.valor_novo || '(vazio)'}</span>
                </p>
              )}
              {l.motivo_indisponivel && (desfeito || l.eh_exclusao) && (
                <p className="mt-1 text-[11px] text-slate-500">{l.motivo_indisponivel}</p>
              )}
              {aviso && (
                <p className={`mt-1.5 text-xs font-bold ${aviso.ok ? 'text-emerald-400' : 'text-amber-300'}`}>{aviso.texto}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
