**Kyndo - Sistema de Gerenciamento de Demandas**

criei esse aplicativo com o intuito de gerir e facilitar as solicitações de tarefas pra desenvolvimento na empresa em que trabalho.

A arquitetura é dividida em um frontend construído em React e uma API REST desenvolvida em Python utilizando FastAPI. O sistema inclui suporte a compilação nativa para Android através do Capacitor.

O quadro funciona no estilo kanban, com colunas configuráveis e arrastar-e-soltar, mas a ideia foi crescendo e hoje ele tem bem mais coisa do que só o quadro: notas, mapas mentais, desenhos, dashboard, log de auditoria e um sistema de cargos com permissões separadas uma a uma.

A interface é escura por padrão, e a versão atual é a v1.7.1 (mostrada no canto da tela).

---

## Funcionalidades

**Quadro e cartões**

Colunas configuráveis, com cor, ordem e a opção de arquivar. Podem ser marcadas como públicas (qualquer pessoa cria cartão nelas) ou privadas.

Colunas podem ser configuradas para alterar o status da demanda automaticamente — por exemplo mover pra "concluído" quando o checklist termina, ou pra "em andamento" quando ele começa.

Cartões com prioridade, prazo, responsáveis, descrição, comentários e checklist de etapas com sub-etapas. Cada etapa aceita uma observação própria.

Filtros de visualização (minhas demandas, por prioridade), ordenação e busca.

**Fundir cartões**

Quando duas pessoas abrem a mesma demanda em dois cartões, dá pra fundir um no outro. Tudo do cartão de origem vai pro destino — etapas, comentários, responsáveis, anexos, sugestões, anotações, mapas mentais, desenhos e o histórico de auditoria — e a origem é apagada.

A descrição da origem é anexada no fim da descrição do destino, junto de qualquer valor que tenha se perdido por conflito (prioridade, prazo, GitHub), pra nada sumir sem deixar registro.

É restrito a administrador e exige digitar CONFIRMO, porque não tem desfazer.

**Tarefas recorrentes**

Um cartão pode ser marcado como recorrente a cada N dias. Quando o prazo vira, o checklist é reiniciado e o cartão volta pra coluna configurada. Se o servidor ficou desligado por vários períodos, ele acerta o próximo vencimento sem disparar várias vezes.

**Sugestões**

Quem não tem permissão pra editar um cartão pode mandar uma sugestão, inclusive propondo um valor novo pra um campo específico. Quem decide aceita ou recusa: ao aceitar é obrigatório informar um prazo de entrega, ao recusar é obrigatório informar o motivo.

Aceitar aplica a mudança no cartão. Se a decisão for revogada depois, o valor anterior volta — mas só se ninguém tiver editado aquele campo à mão no meio do caminho, senão a edição da pessoa é preservada e fica registrado que não deu pra reverter.

Como várias pessoas usam a mesma conta em alguns setores, quem escreve a sugestão precisa se identificar pelo nome.

**Notificações do que mudou**

Cada cartão marca o que você ainda não viu. O contador é de alterações, não de acessos: cartão novo não gera aviso, e quem fez a alteração não recebe aviso da própria mudança. As observações de cada etapa têm o aviso separado, por etapa.

**Anexos**

Upload de arquivos por cartão, até 20MB cada. O nome em disco nunca é o nome enviado pelo usuário, só a extensão é aproveitada. Apagar o cartão apaga os anexos e os arquivos junto.

**Notas, mapas mentais e desenhos**

Aba de notas com editor de texto e editor de canvas pra mapas mentais (blocos ligados por setas). Aba de desenho com canvas livre.

Qualquer nota ou desenho pode ser vinculada a um cartão, deixada pública ou compartilhada com pessoas específicas, com nível de ver ou editar.

**Cronograma e Dashboard**

Cronograma mostra os cartões na linha do tempo pelos prazos.

Dashboard traz total de cartões, distribuição por coluna e por prioridade, atrasados, carga por responsável, tempo médio de conclusão e um resumo das sugestões por status e por quem decidiu.

**Integração com GitHub**

Cada cartão pode apontar pra um repositório, e o cartão mostra informação do pull request vinculado. Precisa de um `GITHUB_TOKEN` no `.env`.

Não mostra status de CI de propósito: a Checks API do GitHub (que é onde o Actions reporta) só é legível por GitHub App, nunca por token pessoal.

**Log de auditoria**

Toda alteração vira uma entrada: campo alterado, valor antigo, valor novo, quem fez e quando. Etapas, sub-etapas, comentários, anexos, sugestões, fusões e reinícios de tarefa recorrente entram no log.

O log respeita a restrição de colunas do cargo — quem só enxerga certas colunas não lê o histórico das outras.

---

## Cargos e permissões

Autenticação e autorização via tokens JWT, com senhas hasheadas via Bcrypt.

O controle de acesso é por cargo, e cada cargo liga ou desliga 17 permissões separadas — gerenciar usuários, gerenciar cargos, ver log de auditoria, gerenciar colunas, reordenar cartões, editar cartão, excluir cartão, editar prioridade, editar prazo, gerenciar etapas, concluir etapas, ver etapas, gerenciar responsáveis, decidir sugestões, entre outras.

Uma pessoa pode ter mais de um cargo, e as permissões somam.

Um cargo também pode ser restrito a colunas específicas. Nesse caso os cartões das outras colunas simplesmente não existem pra ela — a API responde 404 em vez de 403, pra não dar nem pra descobrir que existem.

Três cargos já vêm criados: **Superadmin** (protegido, tem tudo), **Admin** e **Usuário** (não tem nenhuma permissão marcada por padrão).

Painel administrativo integrado para gestão de contas e geração de senhas temporárias — quem entra com senha temporária é obrigado a trocar antes de usar o sistema.

---

## Stack

**Frontend:** React, Tailwind CSS, @hello-pangea/dnd, lucide-react, Vite, Capacitor.

**Backend:** Python, FastAPI, SQLAlchemy, SQLite, Bcrypt, PyJWT, httpx.

---

## Como executar localmente

É necessário ter Node.js e Python 3 instalados no ambiente.

### Configuração do Backend (API)

Clone o repositório e acesse o diretório backend.

Crie e ative o ambiente virtual:

```bash
python -m venv venv
venv\Scripts\activate
```

(Em sistemas baseados em Unix: `source venv/bin/activate`)

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie um arquivo `.env` dentro de `backend/`:

```
SECRET_KEY=uma_chave_longa_e_aleatoria_sua
GITHUB_TOKEN=opcional_so_pra_integracao_com_github
```

O `SECRET_KEY` é o que assina os tokens de login. Sem ele o sistema sobe com uma chave padrão que está no código — serve pra rodar local, mas não use assim em rede.

Inicie o servidor:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8095
```

Nota: O banco de dados (demandas.db) será gerado automaticamente na raiz da pasta backend durante a primeira execução. As migrations rodam sozinhas na inicialização, então atualizar o código não exige mexer no banco.

### Configuração do Frontend

Em um novo terminal, acesse o diretório frontend.

Instale as dependências do projeto:

```bash
npm install
```

Inicie o servidor de desenvolvimento:

```bash
npm run dev
```

O frontend sobe na porta 5176 e descobre o endereço da API sozinho a partir do host que você acessou, então abrir pelo IP da máquina na rede já funciona sem editar nada.

### Atalho pra subir tudo de uma vez

Na raiz do projeto tem o `iniciar.bat`, que sobe backend e frontend em segundo plano (sem janela de terminal) e já abre o navegador. Pode fechar a janela que os servidores continuam rodando. Pra encerrar de verdade, use o `parar.bat`.

### Acesso Inicial

A rotina de inicialização do backend cria uma conta de administração padrão caso o banco de dados esteja vazio:

Usuário: admin

Senha: admin

Troque essa senha antes de deixar o sistema acessível pra qualquer pessoa na rede.

---

## Testes

O backend tem uma suíte de testes cobrindo autenticação, permissões, visibilidade de colunas, auditoria, sugestões, anexos, recorrência, fusão de cartões e as regressões dos bugs já corrigidos.

```bash
cd backend
venv\Scripts\python -m pytest
```

---

## Build para Android

Para gerar o aplicativo e rodar no emulador ou dispositivo físico:

```bash
cd frontend
npm run build
npx cap sync android
npx cap run android
```

Importante: no navegador a API é descoberta sozinha, mas no build nativo não — o app não é servido pelo servidor, então o `window.location.hostname` não aponta pra lugar nenhum útil. Antes de gerar o build, troque a constante `API` no arquivo `frontend/src/api.js` pelo IPv4 da máquina que roda o backend. Apenas usar localhost não funcionará fora do ambiente de desenvolvimento da própria máquina.

---

ps: primeiramente eu tentei utilizar o androidStudio pra rodar o teste do aplicativo atraves do dispositivo virtual que o software disponibiliza
alem de eu nao conseguir fazer rodar por conta do consumo absurdo de RAM que isso requeria do meu pc, eu nao consegui estabelecer a conexão do
banco de dados com o aplicativo de jeito nenhum.
