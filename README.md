# agent-framework-demo

A Python multi-agent workflow demo using Microsoft Agent Framework concepts and SDK orchestration.

## What This App Does

The app runs a simple sequential multi-agent pipeline:

1. Planner creates a task plan (`research -> analyze -> review`)
2. Research agent gathers source-backed data from:
   - local notes in `data/company_notes.txt`
   - external public API (DuckDuckGo)
3. Analysis agent computes metrics and summary
4. Review agent validates safety and approves output

The orchestration is implemented with `agent-framework` + `SequentialBuilder`.

## Prerequisites

- Python 3.10+
- pip

## Setup

### 1. Go to project folder

```bash
cd /d/projects/python/agent-framework-demo
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
```

Git Bash (Windows):

```bash
python -m venv .venv
```

macOS/Linux:

```bash
python3 -m venv .venv
```

### 3. Activate the virtual environment

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Git Bash (Windows):

```bash
source ./.venv/Scripts/activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

## Configuration

Create your environment file from the template:

Windows:

```powershell
Copy-Item .env.example .env
```

Git Bash/macOS/Linux:

```bash
cp .env.example .env
```

Default settings in `.env.example` are enough to run locally.

### Optional: Enable LLM Mode

The app now supports optional LLM-based guide generation with deterministic fallback.

Set in `.env`:

```dotenv
USE_LLM=true
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_ENDPOINT=https://api.openai.com/v1/chat/completions
OPENAI_TIMEOUT=20
LLM_WEB_SEARCH=true
LLM_SEARCH_CONTEXT_SIZE=high
LLM_TOOL_ROUTING=true

ENABLE_COMPLIANCE_CHECK=true
ENABLE_HUMAN_APPROVAL=true
APPROVAL_MODE=auto
APPROVAL_TOKEN=

ENABLE_SECRET_HYGIENE=true
STRICT_SECRET_HYGIENE=false
```

If `USE_LLM=true` but API key/config is missing or the model call fails, the app
automatically falls back to the non-LLM deterministic analyzer.

When `LLM_WEB_SEARCH=true`, the LLM request uses OpenAI web search via the
Agent Framework OpenAI client, allowing online evidence retrieval instead of only
local pre-fetched snippets.

## Start the App

### Run with default goal

```bash
python main.py
```

### Run with a custom goal

```bash
python main.py --goal "Research AI agents for internal productivity tools"
```

If `python` is not in PATH on your machine, use the venv interpreter directly:

```bash
./.venv/Scripts/python.exe main.py
```

## How To Use Prompts

Use the `--goal` argument as your prompt:

```bash
python main.py --goal "<your prompt here>"
```

### Prompt template (recommended)

Use this structure for better outputs:

```text
I want to learn <topic>.
Level: <beginner/intermediate>.
Goal: <what you want to achieve>.
Output format: <guide/checklist/steps>.
```

### Good prompt examples

```bash
python main.py --goal "I want to learn PHP programming. Level: beginner. Goal: build simple web scripts. Output format: step-by-step weekly guide."
python main.py --goal "Teach me Python basics for automation. Level: beginner. Goal: automate file tasks. Output format: 10-day checklist."
python main.py --goal "Explain Microsoft Agent Framework for beginners. Goal: build first multi-agent workflow. Output format: practical roadmap."
```

### Prompt tips

- Be specific about topic and level.
- Ask for a concrete output format (for example: "weekly plan", "checklist", "roadmap").
- Include a clear end goal (for example: "build X in 2 weeks").
- Avoid very short prompts like "teach me coding".

### Online-search LLM mode (recommended)

To let the model search online when answering:

```dotenv
USE_LLM=true
LLM_WEB_SEARCH=true
LLM_SEARCH_CONTEXT_SIZE=high
```

Then run:

```bash
python main.py --goal "I want to learn PHP programming"
```

If LLM/web-search is unavailable, the app automatically falls back to local/API-based deterministic guidance.

## Expected Output

The app prints logs and a final JSON payload:

- `status`
- `final_summary`
- `metrics`
- `references`
- `review_notes`
- `future_controls`

## Project Structure

```text
agent-framework-demo/
|-- main.py
|-- config.py
|-- requirements.txt
|-- .env.example
|-- agents/
|   |-- planner.py
|   |-- researcher.py
|   |-- analyzer.py
|   `-- reviewer.py
|-- tools/
|   |-- file_tools.py
|   |-- api_tools.py
|   `-- safe_tools.py
|-- services/
|   `-- retry_service.py
`-- data/
    `-- company_notes.txt
```

## Guardrails and Reliability

- Prompt safety checks in `tools/safe_tools.py`
- File path traversal protection in `tools/file_tools.py`
- API response validation and timeout in `tools/api_tools.py`
- Retry + exponential backoff in `services/retry_service.py`

### Demo-ready controls added

- Model-directed tool routing in `agents/researcher.py` via `tools/llm_tools.py`
- Evidence/citation verification in `agents/reviewer.py`
- Compliance gate in `agents/compliance.py`
- Human approval gate in `agents/approval.py`
- Observability report in final output (`observability` block)
- Secret hygiene scan at startup via `tools/secret_hygiene.py`

Example token approval mode:

```dotenv
APPROVAL_MODE=token
APPROVAL_TOKEN=approved_for_demo
```

Secret hygiene strict mode (fails run if findings exist):

```dotenv
STRICT_SECRET_HYGIENE=true
```

## Troubleshooting

### `source .../activate` fails in Git Bash

Use a relative path from project root:

```bash
source ./.venv/Scripts/activate
```

### `python: command not found`

Use:

```bash
./.venv/Scripts/python.exe main.py
```

### API/network issues

- Check internet connectivity
- Increase `SEARCH_API_TIMEOUT` in `.env`

## Notes

This project uses `agent-framework` package APIs for workflow execution.
If you later want Azure AI integrations, install preview integration packages where required.

For optional LLM mode in this project, model calls use Microsoft Agent Framework's
OpenAI provider client (`agent_framework_openai.OpenAIChatCompletionClient`).
