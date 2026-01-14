"""FastAPI server for the Payables Agent."""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agentcore import (
    InferenceClient,
    RequestContext,
    EnrichedUser,
    Permission,
)
from agentcore.settings import InferenceSettings

from .agent import PayablesAgent


agent: Optional[PayablesAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    
    settings = InferenceSettings(
        base_url=os.getenv("INFERENCE_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.getenv("INFERENCE_API_KEY", "mock-key"),
        default_model=os.getenv("INFERENCE_DEFAULT_MODEL", "gpt-4"),
    )
    
    inference = InferenceClient(settings)
    agent = PayablesAgent(inference)
    
    print(f"Payables Agent started on port 8002")
    print(f"  Agent ID: {agent.info.agent_id}")
    print(f"  Capabilities: {agent.info.capabilities}")
    
    yield
    
    print("Payables Agent shutting down")


app = FastAPI(
    title="Payables Agent",
    description="Accounts payable domain agent for invoice and payment management",
    version="1.0.0",
    lifespan=lifespan,
)


class QueryRequest(BaseModel):
    query: str
    stream: bool = False


class QueryResponse(BaseModel):
    response: str
    agent_id: str


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "payables"}


@app.get("/capabilities")
async def capabilities():
    if agent is None:
        return {"error": "Agent not initialized"}
    return agent.info.model_dump()


@app.post("/api/v1/query")
async def query(request: QueryRequest):
    if agent is None:
        return {"error": "Agent not initialized"}
    
    user = EnrichedUser(
        user_id=1,
        username="demo_user",
        email="demo@example.com",
        display_name="Demo User",
        entity_id=1,
        entity_name="Demo Corp",
        permissions=frozenset([Permission.BUYER]),
    )
    ctx = RequestContext.create(
        user=user,
        session_id="demo-session",
        request_id="req-001",
    )
    
    if request.stream:
        async def generate():
            async for chunk in agent.handle_query(ctx, request.query):
                yield chunk
        
        return StreamingResponse(generate(), media_type="text/plain")
    else:
        response_text = ""
        async for chunk in agent.handle_query(ctx, request.query):
            response_text += chunk
        
        return QueryResponse(response=response_text, agent_id=agent.info.agent_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
