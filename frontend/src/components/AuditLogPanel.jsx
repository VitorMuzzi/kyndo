import React, { useEffect, useState } from 'react';
import { ScrollText } from 'lucide-react';
import { API, authFetch } from '../api.js';

const ACAO_LABELS = {
  card_criado: 'criou o card',
  card_excluido: 'excluiu o card',
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
  subetapa_criada: 'criou a sub-etapa',
  subetapa_editada: 'editou a sub-etapa',
  subetapa_concluida: 'concluiu a sub-etapa',
  subetapa_reaberta: 'reabriu a sub-etapa',
  subetapa_excluida: 'excluiu a sub-etapa',
  comentario_adicionado: 'comentou',
  sugestao_criada: 'sugeriu uma mudança',
  sugestao_aceita: 'aceitou uma sugestão',
  sugestao_rejeitada: 'recusou uma sugestão',
  sugestao_aceita_sem_aplicar: 'aceitou uma sugestão (alvo não encontrado, nada foi aplicado)',
  sugestao_apagada: 'apagou uma sugestão',
  recorrencia_configurada: 'configurou a recorrência do card',
  recorrencia_desativada: 'desativou a recorrência do card',
  tarefa_recorrente_reiniciada: 'reiniciou automaticamente (tarefa recorrente)',
  anexo_adicionado: 'anexou um arquivo',
  anexo_removido: 'removeu um anexo',
};

function formatData(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('pt-BR');
}

export default function AuditLogPanel() {
  const [logs, setLogs] = useState(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    authFetch(`${API}/audit-log`)
      .then(r => (r.ok ? r.json() : Promise.reject(r)))
      .then(setLogs)
      .catch(() => setErro('Não foi possível carregar o log de auditoria.'));
  }, []);

  return (
    <div>
      <h3 className="text-lg font-bold text-slate-100 mb-4 flex items-center gap-2"><ScrollText size={20}/> Log de Auditoria</h3>
      {erro && <div className="mb-4 text-sm font-bold text-red-400 bg-red-500/10 p-2 rounded">{erro}</div>}
      {!logs && !erro && <p className="text-sm text-slate-500">Carregando...</p>}
      {logs && logs.length === 0 && <p className="text-sm text-slate-500">Nenhuma alteração registrada ainda.</p>}
      <div className="space-y-2 max-h-[60vh] overflow-y-auto custom-scrollbar pr-1">
        {(logs || []).map(l => (
          <div key={l.id} className="p-3 bg-slate-800 border border-slate-700 rounded-xl shadow-sm text-sm">
            <div className="flex justify-between items-start gap-2">
              <p className="text-slate-200">
                <span className="font-bold text-slate-100">{l.usuario}</span>{' '}
                {ACAO_LABELS[l.acao] || l.acao}
                {l.card_titulo && <> em <span className="font-bold text-slate-100">"{l.card_titulo}"</span></>}
                {l.detalhe && <> — <span className="italic text-slate-400">{l.detalhe}</span></>}
              </p>
              <span className="text-[10px] text-slate-500 font-semibold whitespace-nowrap shrink-0">{formatData(l.data)}</span>
            </div>
            {(l.valor_antigo || l.valor_novo) && (
              <p className="mt-1 text-xs text-slate-400">
                <span className="line-through">{l.valor_antigo || '(vazio)'}</span>
                {' → '}
                <span className="font-bold text-slate-200">{l.valor_novo || '(vazio)'}</span>
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
