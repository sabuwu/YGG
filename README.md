# Ygg

Ygg is a Discord bot written in Python. It supports message commands, the
`/ping` application command, and an interactive terminal console that runs
alongside the bot. The Discord client and console share the same `asyncio`
event loop, so the bot can receive messages while the terminal waits for input.

The current version is **0.1.0**. This project provides a small foundation
for building new commands; its current Discord functionality is replying to
`ping` with `🏓 pong!`.

## Contents

- [Features](#features)
- [Requirements and dependencies](#requirements-and-dependencies)
- [Discord setup](#discord-setup)
- [Installation](#installation)
- [Environment configuration](#environment-configuration)
- [Running](#running)
- [Discord commands](#discord-commands)
- [Local terminal](#local-terminal)
- [Logs](#logs)
- [Project structure](#project-structure)
- [Architecture and execution lifecycle](#architecture-and-execution-lifecycle)
- [Tests](#tests)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Current limitations](#current-limitations)
- [Author and license](#author-and-license)

## Features

- Responds to `@ygg ping` sent as text.
- Recognizes real mentions of the bot followed by `ping`.
- Recognizes a mention of the bot's managed role followed by `ping`.
- Registers and globally syncs the `/ping` application command at startup.
- Responds to `/ping` when sent as a regular text message.
- Provides a local console to send messages to server text channels, show help,
  manage logging, and shut down the bot.
- Logs startup, connection, command sync, and handled commands.
- Coordinates shutdown of the Discord client and console.
- Runs without a prompt when standard input is not an interactive terminal.
- Includes automated tests that simulate Discord and terminal input.

## Requirements and dependencies

To run the project, you need:

- **Python 3.14 or newer**. The `.python-version` file selects the **3.14**
  series for tools that honor it.
- Internet access to install dependencies and connect to Discord.
- A Discord bot application and its authentication token.
- Permission to install the bot in a server where you can test it.
- An interactive terminal if you want to use the local console.

Direct dependencies are declared in [pyproject.toml](pyproject.toml):

| Dependency | Declared range | Purpose |
| --- | --- | --- |
| `discord.py` | `>=2.5.0,<3.0.0` | Discord client, events, messages, and `/` commands. |
| `python-dotenv` | `>=1.0.1,<2.0.0` | Loads variables from the `.env` file. |
| `prompt-toolkit` | `>=3.0.0,<4.0.0` | Asynchronous terminal prompt. |
| `rich` | `>=15.0.0` | Displays Discord messages when the interactive console is disabled. |

The package build backend is `uv_build`, in the `>=0.13.1,<0.14.0` range.
[uv.lock](uv.lock) records the resolved dependency versions. Tests use
`unittest` from the Python standard library.

## Discord setup

### Create or select an application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create an application or open the application you will use for Ygg.
3. In the **Bot** section, obtain the bot authentication token.
4. Keep the token available to set `DISCORD_API_KEY`, as described in
   [Environment configuration](#environment-configuration).

Use the **bot** token. The application ID, public key, and client secret are
different values and cannot be used in its place.

### Enable message content

On the **Bot > Privileged Gateway Intents** page, enable **Message Content
Intent** and save the setting.

The code already sets `intents.message_content = True`. This setting must
also be enabled in the portal for the connection to be authorized. The
project uses it to interpret commands sent as text. See the
[discord.py intents documentation](https://discordpy.readthedocs.io/en/stable/intents.html).

### Install the bot in a server

Configure the bot installation with the `bot` and `applications.commands`
scopes. Use the application's install link or the portal's OAuth2 URL
generator, then authorize it in the desired server.

In the channel used for testing, the bot needs **View Channels** and **Send
Messages** permissions. Channel permissions must also allow the person
testing the bot to use application commands to invoke `/ping`.

The [official bot creation guide](https://docs.discord.com/developers/quick-start/getting-started)
covers obtaining credentials and installing Discord applications.

## Installation

Run the commands below from the root of your local project copy, where
`pyproject.toml` and `uv.lock` are located.

### With uv

Install `uv` using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/).
Then prepare Python and the environment:

```sh
uv python install 3.14
uv sync --locked
```

The sync command prepares `.venv` and installs the project and its
dependencies using the lockfile. The `--locked` option requires the lockfile
to be up to date with `pyproject.toml`. You do not need to activate the
virtual environment to use `uv run`. See the [uv projects guide](https://docs.astral.sh/uv/guides/projects/).

### With venv and pip

Alternatively, with Python 3.14 installed, create a virtual environment and
install the package in editable mode.

**Linux or macOS:**

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e .
```

**Windows, in PowerShell:**

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

The `pip` installation follows the ranges in `pyproject.toml`; it does not
automatically use `uv.lock`.

From the project root, `python -m pip install -r requirements.txt` is also
supported. That file delegates to `-e .`, keeping dependency declarations in
`pyproject.toml`.

## Environment configuration

Create or edit a file named `.env` in the project root:

```dotenv
DISCORD_API_KEY=YOUR_BOT_TOKEN_HERE
```

Replace the example value with the real token before starting the bot.

| Variable | Required | Description |
| --- | --- | --- |
| `DISCORD_API_KEY` | Yes | Token used to authenticate the Discord client. |

This is the only configuration variable read directly by the application.
It can also be supplied through the process environment. If the variable
already exists in the environment, `load_dotenv()` preserves that value
instead of replacing it with the `.env` value, as described in the
[python-dotenv documentation](https://bbc2.github.io/python-dotenv/).

`main()` loads the file and validates the token through
`ygg.app.core.config.load_token()` during startup. Importing application modules
does not load `.env` or start the bot. Restart the program after changing the
configuration. If `DISCORD_API_KEY` is missing or empty, startup ends with:

```text
RuntimeError: DISCORD_API_KEY not found in .env
```

Keep the token out of version control. The repository's `.gitignore` excludes
`.env`, `.env.*`, `.venv/`, `__pycache__/`, and compiled Python files.

## Running

After installing the dependencies and configuring the token, run:

```sh
uv run --locked ygg
```

The same entry point can be invoked as a module:

```sh
uv run --locked python -m ygg
```

If you are using the virtual environment directly:

```sh
# Linux or macOS
.venv/bin/python -m ygg
```

```powershell
# Windows
.\.venv\Scripts\python.exe -m ygg
```

The `ygg` console command is declared in `[project.scripts]` and points to
`ygg.__main__:main`. Running it as a module uses the same `main()`. The
`src/ygg/app/app.py` file also calls `main()` when run directly, so you can
start the bot from the IDE's active file with the project's virtual
environment selected. Open the IDE's integrated terminal to use the local
console; debug consoles and output panels might not provide interactive input.

The interactive console shows the YGG logo and asks `enter your name: `.
After a non-empty name, it displays a greeting above the command prompt,
for example:

```text
> hello Alex! 2026-10-19 15:30:00-03:00
 >>>
```

The timestamp is captured after the name is entered, using the computer's
configured local timezone and UTC offset. The logo and greeting remain visible
until the first non-empty command is submitted. Empty input keeps them visible;
clearing the output after a command does not bring them back. Use `help` to list
the available commands.

The prompt alone does not confirm that the bot connected. Startup,
command-sync results, and `Connected to Discord as ...` are recorded in
`logs/ygg_logs.log` while the connection and terminal run concurrently.

## Discord commands

### Message-based ping

| Form | How to send it | Response |
| --- | --- | --- |
| Literal prefix | Type `@ygg ping` as text. | `🏓 pong!` |
| Real mention | Select the bot from Discord's mention list and add `ping`. | `🏓 pong!` |
| Bot role mention | Select Ygg's managed role and add `ping`. | `🏓 pong!` |
| `/ping` text | Send `/ping` as a regular message, without selecting the command from the menu. | `🏓 pong!` |

The textual `@ygg` prefix is fixed and does not depend on the bot's name or
nickname in the server. A real mention is identified by the bot's own ID, in
the internal formats `<@ID>` and `<@!ID>`. The bot's managed role is
identified by `guild.self_role`, in the `<@&ROLE_ID>` format. Other roles are
not accepted as a prefix, even if they have the same name. User and role
mentions use distinct formats in the
[Discord documentation](https://docs.discord.com/developers/reference#message-formatting).

The message parser follows these rules:

- Accepts two tokens: the prefix or mention, followed by `ping`; it also
  accepts `/ping` alone as a textual shortcut.
- Ignores case differences in the text prefix and command.
- Accepts extra spaces, tabs, and line breaks between tokens.
- Ignores messages sent by bots, including Ygg itself.
- Ignores mentions of other users or roles, unknown commands, and extra arguments.

Examples of accepted text:

```text
@ygg ping
@YGG PING
   @ygg    ping
```

Messages such as `ping`, `@yggping`, `@ygg ping now`, or `@ygg help` do not
receive a response in the current implementation.

### Application-command ping

Type `/ping` in Discord and select Ygg's application command. The response
is also `🏓 pong!` and is sent publicly in the interaction. If `/ping` is
sent as a regular message, the bot responds through message handling. This
shortcut works alongside the application command.

`DiscordCommands` registers the command, and `App.setup_hook()` globally syncs
the command tree at startup. The code does not select a development server. The
[CommandTree.sync() documentation](https://discordpy.readthedocs.io/en/stable/interactions/api.html#discord.app_commands.CommandTree.sync)
describes syncing commands with Discord.

If syncing raises `discord.HTTPException`, the error is logged and startup
continues, allowing message commands to be used. This does not guarantee
that a new `/ping` definition was successfully published.

## Local terminal

The local terminal is an interface for controlling the Ygg process. It starts
automatically when `sys.stdin.isatty()` returns `True`.

The input stays on the penultimate terminal row, above a row of control hints.
Output remains visible while typing and sending messages. By default, drag
with the mouse to select text, including channel names, then use your terminal's
copy shortcut (usually Ctrl+Shift+C). Use PageUp/PageDown to scroll.
Incoming messages preserve your position while reading older output.
Press F2 to enable mouse-wheel scrolling; press F2 again to return to native
text selection. The bottom row shows the active mode. PageUp/PageDown work
in either mode.

Use `chat`, select a server, then select a text channel. Entering a
channel loads its latest 100 messages in chronological order, including
attachment URLs. Author names use their server nickname and Discord role
colour, when available; users without a role colour use the terminal's default.
New messages from that channel appear without interrupting
your input. The bot needs **View Channel** and **Read Message History**
permissions to load history. If history cannot be loaded, an error appears
and you can still try sending messages.
Use `exit_channel` to select another channel or `exit_server` to select
another server. Failed sends show the Discord error and keep the channel open.

| Input | Behavior |
| --- | --- |
| `help` | Displays the available local commands. |
| `chat` | Selects a server and channel, loads history, and opens chat. |
| `exit_channel`, `exit_server` | Leaves the current channel or server while in chat. |
| `clear logs` | Clears the terminal screen and disables process logging. |
| `enable logs` | Re-enables logging. |
| `stop`, `exit`, `quit`, or `bye` | Exits the console and bot. |
| Ctrl+C | Cancels server/channel selection or chat and returns to local commands; exits the bot at the local-command prompt. |
| End of input, such as Ctrl+D with empty input in a Unix terminal | Returns from chat to local commands, or exits the bot at the local-command prompt. |
| Empty line | Keeps the console open without taking action. |
| Other text | Displays an unknown-command message and keeps the console open. |

Local commands ignore letter case and leading or trailing whitespace. For
example, `EXIT` and `  exit  ` have the same effect. An optional initial `/`
is accepted, such as `/help`. While in chat, ordinary input is sent to Discord;
use Ctrl+C to return to local commands before issuing `help` or `stop`.

The `ping` and `/ping` commands are used in Discord. Typing them in the local
console displays the unknown-command message.

### Running without a TTY

When input is non-interactive, as in some services, redirections, or IDE
consoles, the prompt is not created. The program logs:

```text
Non-TTY input; running the bot without an interactive prompt.
```

In this mode, the Discord client keeps running and logs remain available. To
stop it, use an interrupt or the process control provided by the terminal or
service running it.

## Logs

The application configures the `logging` module at the `INFO` level, with
this format:

```text
<date and time> [<level>] <logger>: <message>
```

Startup, command-sync results, the connected identity, and each handled
`ping` are logged. HTTP sync failures include a traceback for diagnosis.

Logs are written to `logs/ygg_logs.log`, relative to the directory from
which the program was started. The `logs` directory is created automatically.
The file is retained between runs and is not rotated automatically.

In the interactive console, `clear logs` clears the current screen and
disables Python process logging, including logs from libraries. Use
`enable logs` to turn logging back on. This does not delete entries already
written to the file.

## Project structure

```text
YGG/
├── .env                              # Local configuration containing the token
├── .python-version                   # Python series used by uv
├── pyproject.toml                    # Metadata, dependencies, and ygg entry point
├── requirements.txt                  # pip installation delegating to pyproject.toml
├── uv.lock                           # Resolved dependency versions
├── README.md                         # Project documentation
├── src/
│   └── ygg/
│       ├── __init__.py
│       ├── __main__.py               # Entry point for python -m ygg
│       └── app/
│           ├── __init__.py
│           ├── app.py                # Startup and main()
│           ├── core/
│           │   ├── __init__.py
│           │   ├── config.py         # Environment loading and token validation
│           │   ├── logging.py        # Log directory and logging setup
│           │   └── runtime.py        # Discord/terminal tasks and shutdown
│           ├── discord_bot/
│           │   ├── __init__.py
│           │   ├── client.py         # Discord client and event forwarding
│           │   └── commands.py       # DiscordCommands: text and application commands
│           └── terminal/
│               ├── __init__.py
│               ├── terminal.py       # Terminal session and task coordination
│               ├── commands.py       # TerminalCommands: local commands and navigation
│               ├── session.py        # Layout, input, output, styling, and key bindings
│               └── chat.py           # Channel history, message rendering, and sending
└── tests/
    ├── test_app.py                   # Execution lifecycle and task cleanup
    ├── test_client.py                # Discord commands and non-interactive output
    ├── test_config.py                # Token loading and environment precedence
    ├── test_entrypoints.py           # Direct execution, module execution, and import
    ├── test_gateway.py               # Real discord.py event payloads
    └── test_terminal.py              # Input, help, exit, and cancellation
```

The `.venv/` directory is created during installation and is omitted from the
tree. The `.env` file is local configuration and must be created in each
environment.

## Architecture and execution lifecycle

### Components

| Component | Responsibility |
| --- | --- |
| `ygg.__main__` | Exposes `main()` and starts the application when the package runs as a module. |
| `core.config.load_token()` | Loads `.env`, preserves process-environment values, and validates the token. |
| `core.logging.configure_logging()` | Creates the log directory and configures file logging. |
| `discord_bot.client.App` | Extends `discord.Client`, configures intents, and connects Discord events to commands and terminal output. |
| `App.setup_hook()` | Syncs application commands before connecting to the Gateway. |
| `App.on_ready()` | Logs the connected bot identity. |
| `App.on_message()` | Forwards live messages to the terminal, displays non-interactive output, and dispatches text commands. |
| `discord_bot.commands.DiscordCommands` | Registers application commands, parses text prefixes and mentions, and handles `ping`. |
| `core.runtime.run_app()` | Coordinates the client and terminal tasks and waits for shutdown. |
| `terminal.terminal.Terminal` | Coordinates the terminal session and command task. |
| `terminal.commands.TerminalCommands` | Handles local commands, server/channel selection, and navigation. |
| `terminal.session.TerminalSession` | Maintains the output pane, persistent input, author styling, and keyboard/mouse controls. |
| `terminal.chat.ChannelChat` | Loads history, filters live messages, renders Discord messages, and sends channel input. |

### Flow

1. `main()` loads and checks the token, creates the client, configures logging,
   and starts the event loop with `asyncio.run()`.
2. `run_app()` enters the client's asynchronous context and creates the
   `app.start(token)` task, which authenticates and connects to Discord.
3. If input is interactive, a second task runs
   `Terminal(app).start_terminal()` using a persistent full-screen
   `prompt_toolkit` application and asynchronous input.
4. `asyncio.wait(..., return_when=asyncio.FIRST_COMPLETED)` waits for either
   task to finish.
5. When the console exits, the client task ends, or a failure occurs, the
   remaining tasks are cancelled and awaited. The client context closes the
   connection and associated resources.

Using `prompt_async()` lets the application wait for a line without blocking
Discord event processing. See the
[asynchronous prompts documentation](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html#prompt-in-an-asyncio-application).

## Tests

Run the complete test suite with:

```sh
uv run --locked python -m unittest discover -s tests -v
```

With the virtual environment already prepared, you can also run:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

On Windows, replace `.venv/bin/python` with `\.venv\Scripts\python.exe`.

To run only part of the suite:

```sh
uv run --locked python -m unittest discover -s tests -p 'test_app.py' -v
uv run --locked python -m unittest discover -s tests -p 'test_terminal.py' -v
```

The suite covers the application, its entry points, Gateway event processing,
and the terminal. Tests verify:

- Text prefixes, real mentions, case variations, and whitespace.
- The bot's managed role mention and `/ping` sent as text.
- Messages from bots, mentions of other users, and unrecognized input.
- Registration and response for `/ping`, and command-tree syncing.
- Message commands remaining available after an HTTP sync failure.
- The client and terminal running on the same event loop.
- Task cancellation and client closure on exit or failure.
- Execution without a TTY.
- Help, message sending, exit commands, empty input, unknown text, EOF, and Ctrl+C.
- Channel history, attachments, author colours, live-channel filtering, and send errors.
- Propagation of terminal cancellation.
- Direct execution of `app.py`, module execution, and import without starting the bot.
- `MESSAGE_CREATE` and `INTERACTION_CREATE` dispatch through real
  `discord.py` parsers, with HTTP outputs replaced in tests.

Tests use `unittest.IsolatedAsyncioTestCase`, mocks, and fake tokens. They do
not read the real `.env` file or connect to Discord. As a result, they do not
validate the token, server permissions, or connectivity in a real environment.

## Development

### Add an application command

Discord commands are in
[src/ygg/app/discord_bot/commands.py](src/ygg/app/discord_bot/commands.py).
`App` exposes this handler as `app.commands`. To add, for example, `/hello`:

1. Create a coroutine in `DiscordCommands` with a `discord.Interaction` parameter.
2. Register the coroutine with `tree.command()` inside `DiscordCommands.register()`.
3. Restart the bot to sync the command, then test the interaction in Discord.

Example method to add to `DiscordCommands`:

```python
async def hello(self, interaction: discord.Interaction) -> None:
    await interaction.response.send_message("Hello!")
```

Corresponding registration inside `register(self, tree)`:

```python
tree.command(name="hello", description="Send a greeting.")(self.hello)
```

This registration creates an application command. To also support `@ygg
hello`, add the corresponding handling to `DiscordCommands.handle_message()`, preserving the
author and prefix checks. The two paths are implemented separately.

### Add a local command

Edit [src/ygg/app/terminal/commands.py](src/ygg/app/terminal/commands.py).
Add a method to `TerminalCommands` and dispatch it from `run()` after input
normalization and before the unknown-command message. `send_message()` in
the same class handles server/channel selection and the `exit_channel` and
`exit_server` navigation commands. `Terminal` exposes the handler as
`terminal.commands` and coordinates its execution with the session.

Use `ChannelChat` in [src/ygg/app/terminal/chat.py](src/ygg/app/terminal/chat.py)
for history, formatting, and channel sends. Layout and key bindings live in
[src/ygg/app/terminal/session.py](src/ygg/app/terminal/session.py).
Use asynchronous operations for tasks that need to wait; blocking calls in
the command loop also delay the bot.

### Change dependencies

With the `uv` workflow, add a dependency using:

```sh
uv add package-name
```

`uv` updates the manifest and lockfile. If you edit `pyproject.toml`
manually, update the resolution and environment:

```sh
uv lock
uv sync --locked
```

Review changes to `pyproject.toml` and `uv.lock` together, and run the test
suite after changing project behavior.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `DISCORD_API_KEY not found in .env` | Set a non-empty value in the root `.env` or process environment, then restart the program. |
| `discord.errors.LoginFailure` or authentication failure | Check that the credential is the bot's current token. If it was reset in the portal, update the environment used by the process. |
| Error asking to enable `Message Content Intent` | Enable the intent in the portal's Bot section, save, and restart. The code already requests this access. |
| The bot connects but does not respond to `@ygg ping` | Check the exact text, channel access, and send permission. Also test a real mention of the bot followed by `ping`. |
| `/ping` does not appear | Check the installation's `applications.commands` scope and the sync result in the logs. Make sure you selected the correct Discord application. |
| `Failed to sync / commands` log | Read the logged exception to identify an API or permission failure. Message commands remain available if the connection succeeds. |
| Non-TTY input message and no ` >>> ` prompt | Run in an interactive terminal. This is expected in panels without keyboard input. |
| Behavior is unchanged after editing the code | Stop the current instance and restart with `uv run -m ygg`. A running process does not reload files automatically. |
| `ModuleNotFoundError: No module named 'ygg'` | Install the project with `uv sync --locked` or `python -m pip install -e .` in the environment used to run it. |
| Packages are missing or Python version is incompatible | Check that the IDE and terminal use the `.venv` environment prepared with Python 3.14 or newer. |
| Discord connection failures | Check the logs and verify that the process has network access. |

## Current limitations

- The only functional Discord command is `ping`; examples for extending this
  documentation must be implemented before they become available.
- The text prefix is hard-coded and cannot be configured per server.
- The local terminal sends messages only to text channels; it does not support voice channels.
- Application commands are globally synced at startup.
- The project does not implement a database, settings storage, web dashboard,
  voice commands, or integration with AI services.
- No dedicated hosting, system service, or automatic process restart
  configuration is provided.

## Author and license

The author listed in `pyproject.toml` is **sabuwu**.

The repository does not yet contain a license file or a license declared in
the package metadata.
