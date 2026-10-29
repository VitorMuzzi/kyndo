"""Envio de e-mail por SMTP (Gmail/Google Workspace ou qualquer outro).

Configurado só pelo .env do backend — nada de senha no código ou no banco:

    SMTP_HOST=smtp.gmail.com        (padrão)
    SMTP_PORT=587                   (587 = STARTTLS, 465 = SSL)
    SMTP_USER=kyndo@suaempresa.com.br
    SMTP_PASSWORD=senha de app de 16 letras do Google
    SMTP_FROM=kyndo@suaempresa.com.br   (opcional; padrão = SMTP_USER)
    SMTP_FROM_NAME=Kyndo                (opcional)
    KYNDO_URL=http://192.168.0.10:5176  (endereço que abre o Kyndo, pros links)

Sem SMTP_USER/SMTP_PASSWORD o envio fica desligado e o sistema funciona como
antes (esqueci a senha vira pedido pro administrador).

O envio de verdade roda numa fila em segundo plano: o SMTP do Gmail leva um
ou dois segundos e a tela não pode esperar por isso. Falha de envio vai pro
log do servidor — não derruba a ação que gerou o e-mail."""
import logging
import os
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape

log = logging.getLogger("kyndo.email")
_fila = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kyndo-email")

COR = "#059669"


def configurado():
    return bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def url_kyndo():
    return (os.getenv("KYNDO_URL") or "").strip().rstrip("/")


def remetente():
    return os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or ""


def link(caminho):
    """Link absoluto pro Kyndo, ou None sem KYNDO_URL configurada."""
    base = url_kyndo()
    return f"{base}{caminho}" if base else None


def _html(titulo, paragrafos, botao, rodape):
    corpo = "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.55;color:#1e293b;white-space:pre-wrap">{escape(p)}</p>'
        for p in paragrafos
    )
    if botao and botao[1]:
        corpo += (
            f'<p style="margin:22px 0"><a href="{escape(botao[1], quote=True)}" '
            f'style="background:{COR};color:#ffffff;text-decoration:none;font-weight:bold;'
            f'padding:12px 22px;border-radius:10px;display:inline-block;font-size:15px">{escape(botao[0])}</a></p>'
        )
    rodape_html = escape(rodape or "Este e-mail foi enviado automaticamente pelo Kyndo. Não é preciso responder.")
    return f"""<!doctype html>
<html lang="pt-BR"><body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:14px;overflow:hidden">
<tr><td style="background:{COR};padding:18px 28px">
<span style="color:#ffffff;font-size:22px;font-weight:900;font-style:italic;letter-spacing:-0.5px">KYNDO</span>
</td></tr>
<tr><td style="padding:28px">
<h1 style="margin:0 0 18px;font-size:19px;color:#0f172a">{escape(titulo)}</h1>
{corpo}
</td></tr>
<tr><td style="padding:16px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b;line-height:1.5">{rodape_html}</td></tr>
</table>
</td></tr></table>
</body></html>"""


def _texto(titulo, paragrafos, botao, rodape):
    partes = [titulo, ""] + list(paragrafos)
    if botao and botao[1]:
        partes += ["", f"{botao[0]}: {botao[1]}"]
    partes += ["", "--", rodape or "Este e-mail foi enviado automaticamente pelo Kyndo. Não é preciso responder."]
    return "\n".join(partes)


def montar(para, assunto, paragrafos, botao=None, rodape=None, responder_para=None):
    """`botao` = (texto, url); url None some com o botão. `responder_para`
    faz o "Responder" do leitor ir para essa pessoa, não para o Kyndo."""
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = formataddr((os.getenv("SMTP_FROM_NAME") or "Kyndo", remetente()))
    msg["To"] = para
    if responder_para:
        msg["Reply-To"] = responder_para
    msg["Message-ID"] = make_msgid(domain=(remetente().split("@")[-1] or None))
    msg.set_content(_texto(assunto, paragrafos, botao, rodape))
    msg.add_alternative(_html(assunto, paragrafos, botao, rodape), subtype="html")
    return msg


def _transportar(msg):
    host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    porta = int(os.getenv("SMTP_PORT") or 587)
    contexto = ssl.create_default_context()
    if porta == 465:
        servidor = smtplib.SMTP_SSL(host, porta, timeout=20, context=contexto)
    else:
        servidor = smtplib.SMTP(host, porta, timeout=20)
    with servidor as s:
        if porta != 465:
            s.starttls(context=contexto)
        s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        s.send_message(msg)


def _transportar_com_log(msg):
    try:
        _transportar(msg)
    except Exception:  # noqa: BLE001 — qualquer falha de rede/SMTP só vai pro log
        log.exception("Falha ao enviar e-mail para %s (%s)", msg["To"], msg["Subject"])


def _despachar(msg):
    _fila.submit(_transportar_com_log, msg)


def enviar(para, assunto, paragrafos, botao=None, rodape=None, responder_para=None):
    """Põe o e-mail na fila. Devolve False (sem enviar) se o SMTP não estiver
    configurado ou não houver destinatário."""
    if not configurado() or not para:
        return False
    _despachar(montar(para, assunto, paragrafos, botao, rodape, responder_para))
    return True


def enviar_agora(para, assunto, paragrafos, botao=None, rodape=None):
    """Envia na hora e devolve o erro (texto) ou None — pro botão de teste,
    em que quem configura precisa ver se deu certo."""
    if not configurado():
        return "O envio de e-mail não está configurado no servidor (SMTP_USER e SMTP_PASSWORD no .env)."
    try:
        _transportar(montar(para, assunto, paragrafos, botao, rodape))
    except smtplib.SMTPAuthenticationError:
        return "O servidor de e-mail recusou usuário ou senha. No Gmail, use uma senha de app (não a senha normal da conta)."
    except Exception as e:  # noqa: BLE001
        return f"Não foi possível enviar: {e}"
    return None
