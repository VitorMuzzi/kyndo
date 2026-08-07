import React, { useEffect, useState } from 'react';
import { Shield, Plus, Trash2, Lock } from 'lucide-react';
import { API, authFetch } from '../api.js';

const GRUPOS = [
  { titulo: 'Usuários', chaves: ['gerenciar_usuarios', 'excluir_usuarios', 'trocar_senha_outros', 'gerenciar_cargos', 'ver_log_auditoria'] },
  { titulo: 'Quadro', chaves: ['gerenciar_colunas', 'reordenar_cards', 'criar_card_coluna_privada'] },
  { titulo: 'Cards', chaves: ['editar_card', 'excluir_card', 'editar_prioridade', 'editar_prazo', 'ver_etapas', 'gerenciar_etapas', 'concluir_etapas', 'gerenciar_responsaveis'] },
  { titulo: 'Sugestões', chaves: ['decidir_sugestoes'] },
];

export default function RolesPanel() {
  const [roles, setRoles] = useState([]);
  const [permissoesCatalogo, setPermissoesCatalogo] = useState([]);
  const [colunasDisponiveis, setColunasDisponiveis] = useState([]);
  const [editando, setEditando] = useState(null);
  const [nome, setNome] = useState('');
  const [cor, setCor] = useState('#94a3b8');
  const [permissoes, setPermissoes] = useState({});
  const [colunasRestritas, setColunasRestritas] = useState(false);
  const [colunasVisiveis, setColunasVisiveis] = useState([]);

  const carregarRoles = () => {
    authFetch(`${API}/roles`).then(r => (r.ok ? r.json() : [])).then(setRoles);
  };

  useEffect(() => {
    carregarRoles();
    authFetch(`${API}/permissions`).then(r => (r.ok ? r.json() : [])).then(setPermissoesCatalogo);
    authFetch(`${API}/columns`).then(r => (r.ok ? r.json() : [])).then(setColunasDisponiveis);
  }, []);

  const labelDe = (chave) => permissoesCatalogo.find(p => p.key === chave)?.label || chave;

  const iniciarNovo = () => {
    setEditando({}); setNome(''); setCor('#94a3b8'); setPermissoes({});
    setColunasRestritas(false); setColunasVisiveis([]);
  };
  const iniciarEdicao = (role) => {
    setEditando(role); setNome(role.nome); setCor(role.cor); setPermissoes(role.permissoes || {});
    setColunasRestritas(role.colunas_visiveis != null); setColunasVisiveis(role.colunas_visiveis || []);
  };

  const salvar = async () => {
    const body = { nome, cor, permissoes, colunas_restritas: colunasRestritas, colunas_visiveis: colunasVisiveis };
    if (editando?.id) {
      await authFetch(`${API}/roles/${editando.id}`, { method: 'PUT', body: JSON.stringify(body) });
    } else {
      await authFetch(`${API}/roles`, { method: 'POST', body: JSON.stringify(body) });
    }
    setEditando(null);
    carregarRoles();
  };

  const excluir = async (role) => {
    if (!window.confirm(`Excluir o cargo "${role.nome}"?`)) return;
    await authFetch(`${API}/roles/${role.id}`, { method: 'DELETE' });
    carregarRoles();
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2"><Shield size={20}/> Cargos</h3>
        {!editando && (
          <button onClick={iniciarNovo} className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors">
            <Plus size={14}/> Novo cargo
          </button>
        )}
      </div>

      {editando && (
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-4 mb-4">
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Nome</label>
              <input value={nome} onChange={e => setNome(e.target.value)} disabled={editando.protegido} className="w-full p-2 border rounded-lg outline-none focus:border-emerald-500 disabled:bg-gray-100 disabled:text-gray-400" />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-700 uppercase mb-1">Cor</label>
              <input type="color" value={cor} onChange={e => setCor(e.target.value)} disabled={editando.protegido} className="w-12 h-9 rounded border" />
            </div>
          </div>

          {editando.protegido ? (
            <p className="text-xs text-gray-500 italic">Este cargo é protegido — sempre tem todas as permissões e não pode ser alterado ou excluído.</p>
          ) : (
            <>
              <div className="space-y-3">
                {GRUPOS.map(g => (
                  <div key={g.titulo}>
                    <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">{g.titulo}</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                      {g.chaves.map(chave => (
                        <label key={chave} className="flex items-center gap-2 text-sm text-gray-700 p-1">
                          <input type="checkbox" checked={!!permissoes[chave]} onChange={e => setPermissoes({ ...permissoes, [chave]: e.target.checked })} />
                          {labelDe(chave)}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div>
                <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Colunas visíveis</p>
                {permissoes.gerenciar_colunas ? (
                  <p className="text-xs text-gray-500 italic">Cargos com "Criar, editar, arquivar e reordenar colunas" sempre enxergam o quadro inteiro — a restrição abaixo não se aplica.</p>
                ) : (
                  <>
                    <div className="flex gap-4 mb-2">
                      <label className="flex items-center gap-2 text-sm text-gray-700">
                        <input type="radio" name="colunas-modo" checked={!colunasRestritas} onChange={() => setColunasRestritas(false)} /> Ver todas as colunas
                      </label>
                      <label className="flex items-center gap-2 text-sm text-gray-700">
                        <input type="radio" name="colunas-modo" checked={colunasRestritas} onChange={() => setColunasRestritas(true)} /> Restringir a colunas específicas
                      </label>
                    </div>
                    {colunasRestritas && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                        {colunasDisponiveis.map(c => (
                          <label key={c.id} className="flex items-center gap-2 text-sm text-gray-700 p-1">
                            <input
                              type="checkbox"
                              checked={colunasVisiveis.includes(c.id)}
                              onChange={e => setColunasVisiveis(prev => e.target.checked ? [...prev, c.id] : prev.filter(id => id !== c.id))}
                            />
                            {c.titulo}
                          </label>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          )}

          <div className="flex gap-2">
            {!editando.protegido && <button onClick={salvar} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-bold transition-colors">Salvar</button>}
            <button onClick={() => setEditando(null)} className="px-4 py-2 bg-white border border-gray-200 hover:bg-gray-100 rounded-lg text-sm font-bold text-gray-600 transition-colors">Fechar</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {roles.map(r => (
          <div key={r.id} className="flex justify-between items-center p-3 bg-white border border-gray-200 rounded-xl shadow-sm">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: r.cor }}/>
              <span className="font-bold text-gray-800">{r.nome}</span>
              {r.protegido && <Lock size={12} className="text-gray-400"/>}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => iniciarEdicao(r)} className="text-xs font-bold text-emerald-700 hover:underline">{r.protegido ? 'Ver' : 'Editar'}</button>
              {!r.protegido && (
                <button onClick={() => excluir(r)} className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg transition-colors"><Trash2 size={16}/></button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
