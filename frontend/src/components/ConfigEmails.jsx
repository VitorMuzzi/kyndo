import React, { useEffect, useState } from 'react';
import { CheckCircle2, AlertTriangle, Send } from 'lucide-react';
import { API, authFetch } from '../api.js';

const MODOS = [
  { val: 'opcional', label: 'Opcional', dica: 'cada pessoa escolhe; vem ligado' },
  { val: 'obrigatorio', label: 'Obrigatório', dica: 'ninguém desliga: no mínimo dos próprios cards (cada um pode ampliar)' },
  { val: 'desligado', label: 'Desligado', dica: 'ninguém recebe' },
];

// Aba "E-mails" das Configurações (permissão configurar_emails): situação do
// envio, e-mail de teste e o modo de cada aviso automático.
export default function ConfigEmails() {
  const [config, setConfig] = useState(null);
  const [erro, setErro] = useState('');
  const [teste, setTeste] = useState({ enviando: false, msg: '', ok: false });

  useEffect(() => {
    authFetch(`${API}/config/emails`).then(r => (r.ok ? r.json() : null)).then(setConfig);
  }, []);

  const mudarModo = async (tipo, modo) => {
    setErro('');
    const res = await authFetch(`${API}/config/emails`, { method: 'PUT', body: JSON.stringify({ modos: { [tipo]: modo } }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { setErro(data.detail || 'Não foi possível salvar.'); return; }
    setConfig(data);
  };

  const enviarTeste = async () => {
    setTeste({ enviando: true, msg: '', ok: false });
    const res = await authFetch(`${API}/config/emails/teste`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    setTeste({ enviando: false, msg: res.ok ? data.msg : (data.detail || 'Falhou.'), ok: res.ok });
  };

  if (!config) return <div className="text-sm text-slate-500">Carregando…</div>;

  return (
    <div className="space-y-6">
      <div className={`p-4 rounded-xl border text-sm space-y-1 ${config.configurado ? 'border-emerald-500/30 bg-emerald-500/10' : 'border-amber-500/30 bg-amber-500/10'}`}>
        <div className={`flex items-center gap-2 font-bold ${config.configurado ? 'text-emerald-300' : 'text-amber-300'}`}>
          {config.configurado ? <CheckCircle2 size={16}/> : <AlertTriangle size={16}/>}
          {config.configurado ? `Envio ativo — remetente ${config.remetente}` : 'Envio de e-mail não configurado no servidor'}
        </div>
        {!config.configurado && (
          <p className="text-xs text-amber-200/80">Preencha SMTP_USER e SMTP_PASSWORD no arquivo .env do backend e reinicie o servidor. Enquanto isso, nenhum e-mail sai e o "Esqueci a senha" continua indo para o administrador.</p>
        )}
        {config.configurado && !config.url && (
          <p className="text-xs text-amber-200/80">Falta KYNDO_URL no .env: sem ela os e-mails saem sem link e o "Esqueci a senha" continua indo para o administrador.</p>
        )}
        {config.url && <p className="text-xs text-slate-400">Links dos e-mails apontam para {config.url}</p>}
        {config.configurado && (
          <div className="pt-2 flex flex-wrap items-center gap-3">
            <button onClick={enviarTeste} disabled={teste.enviando}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold disabled:opacity-60">
              <Send size={12}/> {teste.enviando ? 'Enviando…' : 'Enviar e-mail de teste para mim'}
            </button>
            {teste.msg && <span className={`text-xs font-bold ${teste.ok ? 'text-emerald-300' : 'text-red-400'}`}>{teste.msg}</span>}
          </div>
        )}
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-black text-slate-300 uppercase tracking-widest">Avisos automáticos</h3>
        {config.tipos.map((t, i) => (
          <React.Fragment key={t.tipo}>
          {t.grupo !== config.tipos[i - 1]?.grupo && (
            <div className="pt-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">{t.grupo}</div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-800 border border-slate-700 rounded-xl">
            <div className="text-sm text-slate-200 flex-1 min-w-[200px]">
              {t.rotulo}

            </div>
            <div className="flex rounded-lg overflow-hidden border border-slate-700 shrink-0">
              {MODOS.map(m => (
                <button key={m.val} onClick={() => t.modo !== m.val && mudarModo(t.tipo, m.val)} title={m.dica}
                  className={`px-3 py-1.5 text-xs font-bold transition-colors ${t.modo === m.val
                    ? (m.val === 'desligado' ? 'bg-slate-600 text-white' : 'bg-emerald-600 text-white')
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200'}`}>
                  {m.label}
                </button>
              ))}
            </div>
          </div>
          </React.Fragment>
        ))}
        {erro && <p className="text-xs font-bold text-red-400">{erro}</p>}
        <p className="text-[11px] text-slate-500">Os e-mails de segurança (link de nova senha e aviso de senha ou e-mail alterados) sempre são enviados. Cada mudança aqui fica no log de auditoria.</p>
      </div>
    </div>
  );
}
