# Purchasing Agent Example

A complete domain agent implementation for procurement and purchase order management.

## Overview

This example demonstrates:
- Creating a domain agent with `BaseAgent`
- Defining domain-specific tools
- Setting up a FastAPI server
- Agent registration and discovery

## Files

```
purchasing_agent/
├── __init__.py
├── agent.py      # PurchasingAgent class with tools
├── main.py       # FastAPI server
└── README.md     # This file
```

## Quick Start

```bash
# From agentcore directory
cd agentcore
source .venv/bin/activate

# Set API key (optional - uses mock responses if not set)
export INFERENCE_API_KEY=sk-...

# Run the agent
uvicorn examples.purchasing_agent.main:app --port 8001
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8001/health
# {"status": "healthy", "agent": "purchasing"}
```

### Get Capabilities
```bash
curl http://localhost:8001/capabilities
# Returns agent registration info
```

### Query the Agent
```bash
# Simple query
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Find PO 12345"}'

# Streaming response
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is my spend by vendor?", "stream": true}'
```

## Available Tools

The agent has these domain tools:

### search_purchase_orders
Search for purchase orders by PO number, vendor, status, or date range.

```json
{
  "po_number": "12345",
  "vendor_name": "Acme",
  "status": "approved",
  "date_from": "2026-01-01",
  "date_to": "2026-01-31"
}
```

### get_spend_analysis
Analyze spend by vendor, category, month, or quarter.

```json
{
  "group_by": "vendor",  // or "category", "month", "quarter"
  "period": "Q1 2026"
}
```

### search_vendors
Search for vendors by name or category.

```json
{
  "name": "Acme",
  "category": "Office Supplies"
}
```

## Example Queries

Try these queries:
- "Find PO 12345"
- "Show me all approved purchase orders"
- "What's my spend on IT equipment this quarter?"
- "Find vendors for office supplies"
- "Create a purchase order for 10 laptops"

## Customization

To create your own agent based on this example:

1. **Copy this directory** to a new location
2. **Update agent.py**:
   - Change `agent_id`, `name`, `description`
   - Update `capabilities` and `domains`
   - Modify `SYSTEM_PROMPT`
   - Implement your own tools
3. **Update main.py**:
   - Change port and app metadata
   - Add any custom middleware or routes

## Architecture

```
User Query
    │
    ▼
FastAPI Server (main.py)
    │
    ▼
PurchasingAgent.handle_query()
    │
    ├─► InferenceClient (LLM)
    │       │
    │       ▼
    │   Tool Calls (if any)
    │       │
    │       ▼
    │   Tool Execution (_execute_tool)
    │       │
    │       ▼
    │   Final Response
    │
    ▼
Streaming Response
```

## Notes

- Without `INFERENCE_API_KEY`, the agent uses mock tool responses
- The tools return mock data for demonstration
- In production, replace mock implementations with real API calls
