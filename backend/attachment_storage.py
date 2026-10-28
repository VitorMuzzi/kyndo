"""Onde os anexos vivem em disco.

Fica fora de routers/ porque routers/attachments.py e lixeira.py (que apaga
o arquivo quando a lixeira expira) precisam disso."""
import os

# Sobrescrevível por env pra os testes redirecionarem uploads pra um temp
# isolado — mesmo mecanismo que o conftest.py usa pra DATABASE_URL.
UPLOAD_DIR = os.getenv("UPLOAD_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "uploads"
)
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB — dá pra print/PDF sem encher o disco sem querer


def caminho_do_anexo(nome_arquivo: str) -> str:
    return os.path.join(UPLOAD_DIR, nome_arquivo)
