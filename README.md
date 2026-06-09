# alien-fingers

`alien-fingers` is a safety-first natural language CLI agent. You ask it to do shell work in plain language, and it asks an AI provider for structured JSON actions such as shell commands, file reads, Python snippets, web searches, or final answers.

The agent does not execute model output directly. Every action is evaluated by deterministic safety rules and an AI safety reviewer, then shown in a Rich approval UI before it runs.

## Install

```bash
pip install -e .
```

Python 3.11+ is required.

## Initialize

```bash
alien-fingers init
alien-fingers config show
```

The config file is stored at:

```text
~/.alien-fingers/config.json
```

## AI providers

Environment variables override the JSON config. Both `ALIEN_FINGERS_*` and the documented `ALIEN-FINGERS_*` spelling are accepted where the OS allows it.

### OpenAI

```bash
alien-fingers config set provider openai
alien-fingers config set model gpt-4.1
export OPENAI_API_KEY=...
```

### Anthropic

```bash
alien-fingers config set provider anthropic
alien-fingers config set model claude-...
export ANTHROPIC_API_KEY=...
```

### Google Gemini

```bash
alien-fingers config set provider gemini
alien-fingers config set model gemini-...
export GEMINI_API_KEY=...
```

### Ollama local model

```bash
ollama serve
ollama pull llama3.1
alien-fingers config set provider ollama
alien-fingers config set model llama3.1
export OLLAMA_BASE_URL=http://localhost:11434
```

### OpenAI-compatible endpoint

```bash
alien-fingers config set provider openai_compatible
alien-fingers config set model your-model
export OPENAI_COMPATIBLE_BASE_URL=http://localhost:8000/v1
export OPENAI_COMPATIBLE_API_KEY=...
```

## Usage

Start the REPL:

```bash
alien-fingers
alien-fingers repl
```

Run one task:

```bash
alien-fingers run "このディレクトリで一番大きいファイルを探して"
alien-fingers ask "git statusを見て、問題があれば修正案を出して"
```

REPL commands:

```text
/help
/exit
/quit
/status
/auto on
/auto off
/provider openai
/model gpt-4.1
/cwd
/cd path
/config
/clear
```

## Approval UI

Before execution, `alien-fingers` shows:

- Action type
- Command, file path, Python code, or search query
- Purpose
- Risk score and risk level
- Safety reasons
- Safer alternative, when available
- Current working directory
- Timeout

Choices:

```text
y  approve this action
n  reject this action
e  edit shell/python action and re-evaluate
a  auto-approve same-session low-risk actions
q  abort the whole task
```

`blocked` actions are not executable by default. Setting `dangerously_allow_blocked_actions=true` enables a second, explicit confirmation prompt.

## Safety model

Every proposed action is reviewed in two stages:

1. Local deterministic rules detect dangerous patterns such as `rm -rf /`, `sudo`, `mkfs`, `dd if=`, `curl ... | sh`, credential paths, external transmission, recursive permission changes, and destructive operations.
2. The configured AI provider reviews the same action and returns JSON with risk score, risk level, auto-approval eligibility, reasons, and a safer alternative.

The higher risk result wins.

Auto-approval is off by default:

```bash
alien-fingers config set auto_approve true
alien-fingers config set auto_approve false
alien-fingers config set auto_approve_max_risk 20
```

Even with auto-approval enabled, manual approval is always required for dangerous or blocked actions, hard-blocked rule matches, secret access, external sending, privilege escalation, destructive file operations, package installs, and global configuration changes.

## Dedicated Python venv

Python actions run through a dedicated venv:

```text
~/.alien-fingers/python-venv
```

Create it:

```bash
alien-fingers venv init
```

Run Python or pip inside it:

```bash
alien-fingers venv python --version
alien-fingers venv pip install pandas
```

Python action code is written to a temporary file, displayed for approval, executed with a timeout, and its stdout/stderr are fed back to the model as untrusted output.

## Web search

Web search is pluggable:

```bash
alien-fingers config set web_search_backend serper
export SERPER_API_KEY=...

alien-fingers config set web_search_backend tavily
export TAVILY_API_KEY=...

alien-fingers config set web_search_backend duckduckgo
```

If a backend needs an API key and it is missing, the action fails clearly. Search results are passed to the model inside `<untrusted_web_search_results>` and must not be treated as instructions.

## Session logs

JSONL logs are written by default:

```text
~/.alien-fingers/logs/YYYYMMDD-HHMMSS.jsonl
```

Logs include user input, proposed actions, safety evaluations, approval decisions, and execution metadata. Long output is truncated and token/API-key-like values are masked.

Disable logs:

```bash
alien-fingers config set log_sessions false
```

## Prompt injection defenses

Command output, file content, and web search results are always wrapped as untrusted data:

```text
<untrusted_command_output>...</untrusted_command_output>
<untrusted_file_content path="...">...</untrusted_file_content>
<untrusted_web_search_results>...</untrusted_web_search_results>
```

The system prompt instructs the model to ignore instructions inside those blocks and to prioritize the user request, safety policy, and approval flow.

## Known limitations

- AI safety review uses the configured provider, so provider availability affects task execution.
- DuckDuckGo support uses the public HTML endpoint and may change.
- Process tree termination is best-effort on Windows.
- Shell command portability depends on the user's shell and OS.
- The tool is conservative by design; some useful operations require manual approval.
