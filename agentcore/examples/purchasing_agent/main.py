"""Purchasing Agent FastAPI server.

Run with:
    uvicorn examples.purchasing_agent.main:app --reload --port 8001
    
Or:
    python -m examples.purchasing_agent.main
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agentcore import (
    RequestContext,
    EnrichedUser,
    InferenceClient,
    MockRegistryClient,
)
from agentcore.embedding import MockEmbeddingClient
from agentcore.settings.inference import InferenceSettings
from examples.purchasing_agent.agent import PurchasingAgent


agent: Optional[PurchasingAgent] = None
registry: Optional[MockRegistryClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, registry
    
    embedding_client = MockEmbeddingClient()
    registry = MockRegistryClient(embedding_client)
    
    inference_settings = InferenceSettings()
    inference_client = InferenceClient(inference_settings)
    
    agent = PurchasingAgent(inference_client)
    
    await registry.register(agent.info)
    print(f"Registered agent: {agent.info.name}")
    
    yield
    
    await registry.unregister(agent.info.agent_id)
    await inference_client.close()
    print("Agent shutdown complete")


app = FastAPI(
    title="Purchasing Agent",
    description="Domain agent for purchase order and vendor management",
    version="1.0.0",
    lifespan=lifespan,
)


class QueryRequest(BaseModel):
    query: str
    stream: bool = False


class QueryResponse(BaseModel):
    response: str


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "purchasing"}


@app.get("/capabilities")
async def capabilities():
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return agent.info.model_dump()


@app.post("/api/v1/query")
async def query(request: QueryRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    ctx = RequestContext.for_system()
    
    if request.stream:
        async def generate():
            async for chunk in agent.handle_query(ctx, request.query):
                yield chunk
        
        return StreamingResponse(generate(), media_type="text/plain")
    else:
        chunks = []
        async for chunk in agent.handle_query(ctx, request.query):
            chunks.append(chunk)
        
        return QueryResponse(response="".join(chunks))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
