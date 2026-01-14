# AgentCore Examples

This directory contains example code demonstrating AgentCore features.

## Quick Start

### Option 1: Mock Mode (No Setup Required)

```bash
# Run immediately - no API keys, no network needed
python -m examples.free_providers_demo --mock
```

### Option 2: With FREE LLM Providers

```bash
# Groq (recommended - very fast, free tier)
export GROQ_API_KEY=gsk_...  # Get from https://console.groq.com

# OR Ollama (100% local)
ollama pull llama3.2

# Run the multi-agent demo
python -m examples.free_providers_demo
```

## Examples

### 1. Free Providers Demo (`free_providers_demo.py`) ⭐ RECOMMENDED

Test 2 domain agents (Purchasing + Payables) with semantic discovery.

```bash
# QUICKEST: Mock mode (no setup, no network)
python -m examples.free_providers_demo --mock

# WITH REAL LLM: Set API key and run
pip install sentence-transformers  # Optional: better semantic search
export GROQ_API_KEY=gsk_...        # Get from https://console.groq.com
python -m examples.free_providers_demo
```

**Supported FREE Providers:**
| Provider | Sign Up | Model |
|----------|---------|-------|
| Groq | https://console.groq.com | llama-3.1-8b-instant |
| Together.ai | https://api.together.xyz | Llama-3.2-3B-Instruct |
| OpenRouter | https://openrouter.ai | llama-3.1-8b:free |
| Ollama | https://ollama.ai | llama3.2 (local) |

### 2. Multi-Agent Demo (`multi_agent_demo.py`)

Test Purchasing + Payables agents with mock inference.

```bash
python -m examples.multi_agent_demo
```

Shows routing, discovery, and parallel agent execution without real LLM calls.

### 3. Basic Demo (`demo.py`)

Quick demonstration of semantic agent discovery.

```bash
python -m examples.demo
```

**What it shows:**
- Registering 4 sample agents (Purchasing, Payables, HR, IT Support)
- Semantic discovery - finding agents via natural language
- Query routing decisions
- Heartbeat management

### 4. Purchasing Agent (`purchasing_agent/`)

Complete domain agent as FastAPI server.

```bash
uvicorn examples.purchasing_agent.main:app --port 8001
```

### 5. Payables Agent (`payables_agent/`)

Accounts payable domain agent as FastAPI server.

```bash
uvicorn examples.payables_agent.main:app --port 8002
```

## Running 2 Agents Together

```bash
# Terminal 1: Purchasing Agent
uvicorn examples.purchasing_agent.main:app --port 8001

# Terminal 2: Payables Agent
uvicorn examples.payables_agent.main:app --port 8002

# Terminal 3: Test queries
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Find PO 12345"}'

curl -X POST http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show AP aging report"}'
```

## Environment Variables

```bash
# FREE Provider Options (pick one)
GROQ_API_KEY=gsk_...           # Groq free tier
TOGETHER_API_KEY=...           # Together.ai
OPENROUTER_API_KEY=...         # OpenRouter

# Or use OpenAI (paid)
INFERENCE_BASE_URL=https://api.openai.com/v1
INFERENCE_API_KEY=sk-...
INFERENCE_DEFAULT_MODEL=gpt-4
```

## Local Embeddings (FREE)

Install sentence-transformers for completely free local embeddings:

```bash
pip install sentence-transformers
```

The demo will automatically use the `all-MiniLM-L6-v2` model (~90MB, runs locally).
