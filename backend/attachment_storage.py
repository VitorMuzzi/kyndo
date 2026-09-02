"""Onde os anexos vivem em disco e como somem junto com o card.

Fica fora de routers/ porque tanto routers/attachments.py quanto
routers/cards.py precisam disso — um router importando o outro só pra
apagar arquivo seria pior."""
import os

# Sobrescrevível por env pra os testes redirecionarem uploads pra um temp
# isolado — mesmo mecanismo que o conftest.py usa pra DATABASE_URL.
UPLOAD_DIR = os.getenv("UPLOAD_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "uploads"
)
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB — dá pra print/PDF sem encher o disco sem querer


def caminho_do_anexo(nome_arquivo: str) -> str:
    return os.path.join(UPLOAD_DIR, nome_arquivo)


def purgar_anexos_do_card(db, card_id: str) -> int:
    """Apaga as linhas de AttachmentDB do card e os arquivos correspondentes.
    Sem isso, excluir um card deixa anexo órfão: linha viva apontando pra um
    card que não existe mais, o que faz a checagem de visibilidade do download
    ser pulada e o arquivo virar público. Não faz commit."""
    from models import AttachmentDB  # import tardio: models importa database, que lê env

    linhas = db.query(AttachmentDB).filter(AttachmentDB.card_id == card_id).all()
    for a in linhas:
        caminho = caminho_do_anexo(a.nome_arquivo)
        if os.path.isfile(caminho):
            try:
                os.remove(caminho)
            except OSError:
                # Arquivo travado/já sumido não pode impedir a exclusão do card —
                # a linha do banco some de qualquer jeito, que é o que abre o buraco.
                pass
        db.delete(a)
    return len(linhas)
