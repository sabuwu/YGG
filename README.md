# Ygg

Ygg é um bot do Discord escrito em Python, com comandos por mensagem, comando
`/ping` e um console interativo no terminal que executa o programa. O cliente
do Discord e o console usam o mesmo loop de eventos do `asyncio`, permitindo
receber mensagens enquanto o terminal aguarda entrada.

A versão atual é **0.1.0**. O projeto oferece uma base pequena para desenvolver
novos comandos; a funcionalidade disponível no Discord é responder a `ping`
com `🏓 pong!`.

## Sumário

- [Funcionalidades](#funcionalidades)
- [Requisitos e dependências](#requisitos-e-dependências)
- [Configuração do Discord](#configuração-do-discord)
- [Instalação](#instalação)
- [Configuração do ambiente](#configuração-do-ambiente)
- [Execução](#execução)
- [Comandos do Discord](#comandos-do-discord)
- [Terminal local](#terminal-local)
- [Logs](#logs)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Arquitetura e ciclo de execução](#arquitetura-e-ciclo-de-execução)
- [Testes](#testes)
- [Desenvolvimento](#desenvolvimento)
- [Solução de problemas](#solução-de-problemas)
- [Limitações atuais](#limitações-atuais)
- [Autoria e licença](#autoria-e-licença)

## Funcionalidades

- Resposta a `@ygg ping` enviado como texto.
- Reconhecimento de menções reais ao bot, seguidas de `ping`.
- Reconhecimento da menção ao cargo gerenciado do próprio bot, seguida de `ping`.
- Registro e sincronização global do comando `/ping` na inicialização.
- Resposta a `/ping` quando enviado como mensagem de texto comum.
- Console local com ajuda e comandos para encerrar o programa.
- Logs de inicialização, conexão, sincronização e comandos atendidos.
- Encerramento coordenado do cliente Discord e do console.
- Execução sem prompt quando a entrada não é um terminal interativo.
- Testes automatizados que simulam o Discord e a entrada do terminal.

## Requisitos e dependências

Para executar o projeto, são necessários:

- **Python 3.14 ou superior**. O arquivo `.python-version` seleciona a série
  **3.14** para ferramentas que respeitam esse arquivo.
- Acesso à internet para instalar dependências e conectar ao Discord.
- Uma aplicação com bot no Discord e seu token de autenticação.
- Permissão para instalar o bot em um servidor onde você possa testá-lo.
- Um terminal interativo, caso queira utilizar o console local.

As dependências diretas estão declaradas em [pyproject.toml](pyproject.toml):

| Dependência | Intervalo declarado | Uso |
| --- | --- | --- |
| `discord.py` | `>=2.5.0,<3.0.0` | Cliente Discord, eventos, mensagens e comandos `/`. |
| `python-dotenv` | `>=1.0.1,<2.0.0` | Carregamento de variáveis do arquivo `.env`. |
| `prompt-toolkit` | `>=3.0.0,<4.0.0` | Prompt assíncrono do terminal. |

O backend de construção do pacote é `uv_build`, no intervalo
`>=0.13.1,<0.14.0`. O arquivo [uv.lock](uv.lock) registra as versões resolvidas
das dependências. Os testes usam `unittest`, da biblioteca padrão do Python.

## Configuração do Discord

### Criar ou selecionar a aplicação

1. Acesse o [Discord Developer Portal](https://discord.com/developers/applications).
2. Crie uma aplicação ou abra a aplicação que será utilizada pelo Ygg.
3. Na seção **Bot**, obtenha o token de autenticação do bot.
4. Guarde esse token para preencher `DISCORD_API_KEY`, conforme a seção
   [Configuração do ambiente](#configuração-do-ambiente).

Use o token do **bot**. O ID da aplicação, a chave pública e o client secret
são valores diferentes e não substituem essa credencial.

### Habilitar o conteúdo das mensagens

Na página **Bot > Privileged Gateway Intents**, habilite
**Message Content Intent** e salve a configuração.

O código já define `intents.message_content = True`. A configuração precisa
estar habilitada também no portal para que essa conexão seja autorizada.
O projeto usa esse acesso para interpretar comandos enviados como texto.
Veja a [documentação de intents do discord.py](https://discordpy.readthedocs.io/en/stable/intents.html).

### Instalar no servidor

Configure a instalação do bot no servidor com os escopos `bot` e
`applications.commands`. Utilize o link de instalação da aplicação ou o
gerador de URL OAuth2 do portal e conclua a autorização no servidor desejado.

No canal usado para testes, o bot deve ter as permissões **View Channels**
(ver canais) e **Send Messages** (enviar mensagens). As permissões do canal
também precisam permitir que a pessoa que está testando use comandos de
aplicação para chamar `/ping`.

O [guia oficial de criação de bots](https://docs.discord.com/developers/quick-start/getting-started)
explica a obtenção das credenciais e a instalação de aplicações no Discord.

## Instalação

Execute os comandos abaixo na raiz da cópia local do projeto, onde estão
`pyproject.toml` e `uv.lock`.

### Com uv

Instale o `uv` conforme as [instruções oficiais](https://docs.astral.sh/uv/getting-started/installation/).
Depois, prepare o Python e o ambiente:

```sh
uv python install 3.14
uv sync --locked
```

O comando de sincronização prepara `.venv` e instala o projeto e suas
dependências usando o lockfile. A opção `--locked` exige que ele esteja
atualizado em relação ao `pyproject.toml`. Não é necessário ativar o ambiente
virtual para usar `uv run`. Consulte o [guia de projetos do uv](https://docs.astral.sh/uv/guides/projects/).

### Com venv e pip

Como alternativa, com Python 3.14 instalado, crie um ambiente virtual e
instale o pacote em modo editável.

**Linux ou macOS:**

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e .
```

**Windows, no PowerShell:**

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

A instalação com `pip` respeita os intervalos do `pyproject.toml`; ela não
utiliza automaticamente o `uv.lock`.

## Configuração do ambiente

Crie ou edite um arquivo chamado `.env` na raiz do projeto:

```dotenv
DISCORD_API_KEY=COLOQUE_O_TOKEN_DO_BOT_AQUI
```

Substitua o valor de exemplo pelo token real antes de iniciar o bot.

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `DISCORD_API_KEY` | Sim | Token utilizado para autenticar o cliente no Discord. |

Essa é a única variável de configuração lida diretamente pela aplicação.
Ela também pode ser fornecida pelo ambiente do processo. Quando uma variável
já existe no ambiente, `load_dotenv()` preserva esse valor em vez de
substituí-lo pelo conteúdo do `.env`, conforme a [documentação do python-dotenv](https://bbc2.github.io/python-dotenv/).

O arquivo é carregado durante a importação de `ygg.app.app`. Reinicie o
programa depois de alterar a configuração. Se `DISCORD_API_KEY` estiver
ausente ou vazia, a inicialização termina com:

```text
RuntimeError: DISCORD_API_KEY not found in .env
```

Mantenha o token fora do versionamento. Ao configurar as exclusões do Git,
inclua `.env`, `.venv/` e `__pycache__/`; o projeto atualmente não fornece
um arquivo `.gitignore`.

## Execução

Depois de instalar as dependências e configurar o token, execute:

```sh
uv run --locked ygg
```

O mesmo ponto de entrada pode ser chamado como módulo:

```sh
uv run --locked python -m ygg
```

Se estiver usando diretamente o ambiente virtual:

```sh
# Linux ou macOS
.venv/bin/python -m ygg
```

```powershell
# Windows
.\.venv\Scripts\python.exe -m ygg
```

O comando de console `ygg` está declarado em `[project.scripts]` e aponta
para `ygg.__main__:main`. A execução como módulo passa pelo mesmo `main()`.
O arquivo `src/ygg/app/app.py` também chama `main()` quando executado
diretamente, permitindo iniciar o bot pelo arquivo ativo da IDE com o
ambiente virtual do projeto selecionado.
Abra o terminal integrado da IDE para utilizar o console local; consoles de
depuração ou painéis de saída podem não oferecer entrada interativa.

Durante uma inicialização bem-sucedida, aparecem mensagens como:

```text
Iniciando Ygg...
Terminal do YGG iniciado.
Comandos locais: ajuda/help para ver esta mensagem; stop/exit/quit/bye para encerrar o bot.
1 comando(s) / sincronizado(s).
Conectado ao Discord como <nome do bot>. Use @ygg ping ou /ping.
YGG >
```

O exemplo omite os prefixos de data e nível dos logs. A ordem das mensagens
pode variar porque a conexão e o terminal são executados de forma concorrente.
A presença do prompt, por si só, não confirma a conexão: aguarde o log
`Conectado ao Discord como ...`.

## Comandos do Discord

### Ping por mensagem

| Forma | Como enviar | Resposta |
| --- | --- | --- |
| Prefixo literal | Digite `@ygg ping` como texto. | `🏓 pong!` |
| Menção real | Selecione o bot na lista de menções do Discord e acrescente `ping`. | `🏓 pong!` |
| Menção ao cargo do bot | Selecione o cargo gerenciado do Ygg e acrescente `ping`. | `🏓 pong!` |
| Texto `/ping` | Envie `/ping` como mensagem comum, mesmo sem selecionar o comando no menu. | `🏓 pong!` |

O prefixo textual `@ygg` é fixo e independe do nome ou apelido do bot no
servidor. Uma menção real é identificada pelo ID do próprio bot, nos formatos
internos `<@ID>` e `<@!ID>`.
O cargo gerenciado do próprio bot é identificado por `guild.self_role`, no
formato `<@&ID_DO_CARGO>`. Outros cargos, mesmo com o mesmo nome, não são
aceitos como prefixo. Usuários e cargos têm formatos de menção distintos na
[documentação do Discord](https://docs.discord.com/developers/reference#message-formatting).

O interpretador de mensagens segue estas regras:

- Aceita dois elementos: o prefixo ou a menção, seguido de `ping`; também
  aceita `/ping` sozinho como atalho textual.
- Ignora diferenças entre maiúsculas e minúsculas no prefixo textual e no comando.
- Aceita espaços extras, tabulações e quebras de linha entre os elementos.
- Ignora mensagens enviadas por bots, inclusive pelo próprio Ygg.
- Ignora menções a outros usuários ou cargos, comandos desconhecidos e argumentos adicionais.

Exemplos de texto aceito:

```text
@ygg ping
@YGG PING
   @ygg    ping
```

Mensagens como `ping`, `@yggping`, `@ygg ping agora` ou `@ygg ajuda` não
produzem resposta na implementação atual.

### Ping por comando de aplicação

Digite `/ping` no Discord e selecione o comando da aplicação Ygg. A resposta
também é `🏓 pong!` e é enviada publicamente na interação.
Se `/ping` for enviado como uma mensagem comum, o bot responde pelo
tratamento de mensagens. Esse atalho funciona junto ao comando de aplicação.

O comando é registrado em `App.__init__()` e sincronizado globalmente em
`setup_hook()`. Não há seleção de servidor de desenvolvimento no código.
A [documentação de CommandTree.sync()](https://discordpy.readthedocs.io/en/stable/interactions/api.html#discord.app_commands.CommandTree.sync)
descreve a sincronização dos comandos com o Discord.

Se a sincronização lançar `discord.HTTPException`, o erro é registrado e a
inicialização continua, permitindo usar os comandos por mensagem. Isso não
garante que uma nova definição de `/ping` tenha sido publicada com sucesso.

## Terminal local

O terminal local é uma interface para controlar o processo do Ygg. Ele é
iniciado automaticamente quando `sys.stdin.isatty()` retorna `True`.

| Entrada | Comportamento |
| --- | --- |
| `ajuda` ou `help` | Exibe os comandos locais disponíveis. |
| `stop`, `exit`, `quit` ou `bye` | Encerra o console e o bot. |
| Ctrl+C | Interrompe a execução e encerra o programa. |
| Fim da entrada, como Ctrl+D em um terminal Unix | Encerra o console e o bot. |
| Linha vazia | Mantém o console aberto, sem executar uma ação. |
| Outro texto | Exibe uma mensagem de comando desconhecido e mantém o console aberto. |

Os comandos locais ignoram maiúsculas, minúsculas e espaços nas extremidades.
Por exemplo, `EXIT` e `  exit  ` têm o mesmo efeito.

Os comandos `ping` e `/ping` são usados no Discord. Digitá-los no console
local resulta na mensagem de comando desconhecido.

### Execução sem TTY

Quando a entrada não é interativa, como em certos serviços, redirecionamentos
ou consoles de IDE, o prompt não é criado. O programa registra:

```text
Entrada sem TTY; o bot será executado sem prompt interativo.
```

Nesse modo, o cliente Discord continua executando e os logs permanecem
disponíveis. Para encerrar, use a interrupção ou o controle do processo
oferecido pelo terminal ou pelo serviço responsável por executá-lo.

## Logs

A aplicação configura o módulo `logging` no nível `INFO`, com o formato:

```text
<data e hora> [<nível>] <logger>: <mensagem>
```

São registrados a inicialização, o resultado da sincronização de comandos,
a identidade conectada e cada `ping` atendido. Falhas HTTP na sincronização
incluem o traceback para diagnóstico.

O contexto `patch_stdout()` permanece ativo durante a execução para que as
saídas de outras tarefas sejam exibidas junto ao prompt do `prompt-toolkit`.
O projeto não configura arquivo de logs nem rotação; a saída fica no console
e pode ser capturada pelo ambiente que executa o processo.

## Estrutura do projeto

```text
YGG/
├── .env                              # Configuração local com o token
├── .python-version                   # Série de Python utilizada pelo uv
├── pyproject.toml                    # Metadados, dependências e entrada ygg
├── uv.lock                           # Versões resolvidas das dependências
├── README.md                         # Documentação do projeto
├── src/
│   └── ygg/
│       ├── __init__.py
│       ├── __main__.py               # Entrada por python -m ygg
│       └── app/
│           ├── __init__.py
│           ├── app.py                # Cliente, comandos e coordenação das tarefas
│           └── ygg_terminal/
│               ├── __init__.py
│               └── terminal.py       # Prompt e comandos locais
└── tests/
    ├── test_app.py                   # Comandos Discord e ciclo de execução
    ├── test_entrypoints.py           # Execução direta, como módulo e importação
    ├── test_gateway.py               # Payloads reais dos eventos do discord.py
    └── test_terminal.py              # Entrada, ajuda, saída e cancelamento
```

O diretório `.venv/` é criado durante a instalação e foi omitido da árvore.
O arquivo `.env` é uma configuração local, que deve ser criado em cada ambiente.

## Arquitetura e ciclo de execução

### Componentes

| Componente | Responsabilidade |
| --- | --- |
| `ygg.__main__` | Expõe `main()` e inicia a aplicação quando o pacote é executado como módulo. |
| `App` | Especializa `discord.Client`, configura intents e registra a árvore de comandos. |
| `App.setup_hook()` | Sincroniza os comandos de aplicação antes da conexão ao Gateway. |
| `App.on_ready()` | Registra a identidade do bot conectado. |
| `App.on_message()` | Interpreta o comando textual ou a menção e responde ao `ping`. |
| `App.ping()` | Responde à interação `/ping`. |
| `run_app()` | Coordena as tarefas do cliente e do terminal e aguarda seu encerramento. |
| `Terminal.start_terminal()` | Aguarda entrada assíncrona e trata os comandos locais. |

### Fluxo

1. A importação de `app.py` carrega as variáveis do `.env`.
2. `main()` cria o cliente, verifica o token, configura os logs e abre o
   loop com `asyncio.run()`.
3. `run_app()` entra no contexto assíncrono do cliente e cria a tarefa
   `app.start(token)`, responsável por autenticar e conectar ao Discord.
4. Se houver entrada interativa, uma segunda tarefa executa
   `Terminal().start_terminal()` usando `PromptSession.prompt_async()`.
5. `asyncio.wait(..., return_when=asyncio.FIRST_COMPLETED)` aguarda o término
   de uma das tarefas.
6. Ao sair do console, terminar a tarefa do cliente ou ocorrer uma falha,
   as tarefas restantes são canceladas e aguardadas. O contexto do cliente
   fecha a conexão e os recursos associados.

O uso de `prompt_async()` permite aguardar uma linha sem bloquear o
processamento dos eventos do Discord. Consulte a [documentação de prompts assíncronos](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html#prompt-in-an-asyncio-application).

## Testes

Para executar toda a suíte:

```sh
uv run --locked python -m unittest discover -s tests -v
```

Com o ambiente virtual já preparado, também é possível executar:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

No Windows, substitua `.venv/bin/python` por `.\.venv\Scripts\python.exe`.

Para executar somente uma parte da suíte:

```sh
uv run --locked python -m unittest discover -s tests -p 'test_app.py' -v
uv run --locked python -m unittest discover -s tests -p 'test_terminal.py' -v
```

A suíte cobre a aplicação, seus pontos de entrada, o processamento de eventos
do Gateway e o terminal. Os testes verificam:

- Prefixo textual, menções reais, variações de caixa e espaços.
- Menção ao cargo gerenciado do próprio bot e `/ping` enviado como texto.
- Mensagens de bots, menções a outros usuários e entradas não reconhecidas.
- Registro e resposta de `/ping` e sincronização da árvore de comandos.
- Continuidade dos comandos por mensagem após falha HTTP na sincronização.
- Execução do cliente e do terminal no mesmo loop.
- Cancelamento das tarefas e fechamento do cliente em saída ou falha.
- Execução sem TTY.
- Ajuda, comandos de saída, entrada vazia, texto desconhecido, EOF e Ctrl+C.
- Propagação do cancelamento do terminal.
- Execução direta de `app.py`, execução como módulo e importação sem iniciar o bot.
- Encaminhamento de `MESSAGE_CREATE` e `INTERACTION_CREATE` pelos parsers
  reais do `discord.py`, com as saídas HTTP substituídas nos testes.

Os testes usam `unittest.IsolatedAsyncioTestCase`, mocks e tokens fictícios.
Eles não leem o `.env` real nem se conectam ao Discord. Portanto, não validam
o token, as permissões do servidor ou a conectividade de um ambiente real.

## Desenvolvimento

### Adicionar um comando de aplicação

Os comandos atuais ficam em [src/ygg/app/app.py](src/ygg/app/app.py).
Para adicionar, por exemplo, `/ola`:

1. Crie uma coroutine na classe `App` com um parâmetro `discord.Interaction`.
2. Registre essa coroutine na árvore dentro de `App.__init__()`, depois da
   criação de `self.tree`.
3. Reinicie o bot para executar a sincronização e teste a interação no Discord.

Exemplo de método a adicionar à classe `App`:

```python
async def ola(self, interaction: discord.Interaction) -> None:
    await interaction.response.send_message("Olá!")
```

Registro correspondente dentro de `__init__()`:

```python
self.tree.command(name="ola", description="Envia uma saudação.")(self.ola)
```

Esse registro cria o comando de aplicação. Para oferecer também `@ygg ola`,
adicione o tratamento correspondente em `on_message()`, preservando as
verificações de autor e prefixo. Os dois caminhos são implementados separadamente.

### Adicionar um comando local

Edite [src/ygg/app/ygg_terminal/terminal.py](src/ygg/app/ygg_terminal/terminal.py)
e acrescente o tratamento depois da normalização da entrada e antes da
mensagem de comando desconhecido. Use operações assíncronas para tarefas
que precisam aguardar; chamadas bloqueantes nesse loop atrasam também o bot.

### Alterar dependências

No fluxo com `uv`, adicione uma dependência com:

```sh
uv add nome-do-pacote
```

O `uv` atualiza o manifesto e o lockfile. Se editar `pyproject.toml`
manualmente, atualize a resolução e o ambiente:

```sh
uv lock
uv sync --locked
```

Revise as alterações de `pyproject.toml` e `uv.lock` em conjunto e execute
a suíte de testes depois de modificar o comportamento do projeto.

## Solução de problemas

| Sintoma | O que verificar |
| --- | --- |
| `DISCORD_API_KEY not found in .env` | Configure um valor não vazio no `.env` da raiz ou no ambiente do processo e reinicie o programa. |
| `discord.errors.LoginFailure` ou falha de autenticação | Confira se a credencial é o token atual do bot. Se ela foi substituída no portal, atualize o ambiente utilizado pelo processo. |
| Erro pedindo para ativar `Message Content Intent` | Habilite o intent na seção Bot do portal, salve e reinicie. O código já solicita esse acesso. |
| O bot conecta, mas não responde a `@ygg ping` | Confira o texto exato, o acesso ao canal e a permissão de envio. Teste também uma menção real ao próprio bot seguida de `ping`. |
| `/ping` não aparece | Confira a instalação com `applications.commands` e o resultado da sincronização nos logs. Confirme que está selecionando a aplicação correta no Discord. |
| Log `Não foi possível sincronizar os comandos /` | Leia a exceção registrada para identificar a falha de API ou permissão. Os comandos por mensagem permanecem disponíveis se a conexão for concluída. |
| Mensagem de entrada sem TTY e ausência de `YGG > ` | Execute em um terminal interativo. Esse comportamento é esperado em painéis sem entrada de teclado. |
| O comportamento continua antigo depois de alterar o código | Encerre a instância atual e inicie novamente com `uv run -m ygg`. O processo em execução não recarrega os arquivos automaticamente. |
| `ModuleNotFoundError: No module named 'ygg'` | Instale o projeto com `uv sync --locked` ou `python -m pip install -e .` no ambiente usado para executar. |
| Pacotes não encontrados ou versão de Python incompatível | Confira se a IDE e o terminal usam o ambiente `.venv` preparado com Python 3.14 ou superior. |
| Falhas de conexão ao Discord | Consulte os logs e verifique o acesso à rede do processo. |

## Limitações atuais

- O único comando funcional no Discord é `ping`; os exemplos de extensão
  desta documentação precisam ser implementados para ficarem disponíveis.
- O prefixo textual é definido no código e não possui configuração por servidor.
- O terminal local oferece ajuda e encerramento, sem envio de comandos ao Discord.
- A sincronização de comandos de aplicação é global e ocorre na inicialização.
- O projeto não implementa banco de dados, armazenamento de configurações,
  painel web, comandos de voz ou integração com serviços de IA.
- Não há configuração própria de hospedagem, serviço de sistema ou reinício
  automático do processo.

## Autoria e licença

O autor declarado no `pyproject.toml` é **sabuwu**.

O repositório ainda não contém um arquivo de licença nem uma licença declarada
nos metadados do pacote.
