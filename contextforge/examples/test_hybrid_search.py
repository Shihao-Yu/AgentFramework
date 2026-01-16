"""
ContextForge Hybrid Search Testing

Demonstrates:
1. BM25 (keyword) search
2. Vector (semantic) search
3. Hybrid search with RRF fusion
4. Score interpretation

Prerequisites:
- PostgreSQL with pgvector extension
- Database with knowledge_nodes populated
- Run: python examples/test_hybrid_search.py
"""

import asyncio
import os
from dotenv import load_dotenv


# Test queries with expected behavior
TEST_CASES = [
    {
        "query": "pending orders",
        "description": "Exact keyword match - should score high on BM25",
        "node_types": ["schema_field", "example"],
    },
    {
        "query": "orders that are waiting to be processed",
        "description": "Semantic match - should score high on Vector",
        "node_types": ["schema_field", "example"],
    },
    {
        "query": "customer email address",
        "description": "Mixed match - both BM25 and Vector should contribute",
        "node_types": ["schema_field"],
    },
]


async def main():
    load_dotenv()
    
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from app.clients.embedding_client import EmbeddingClient
    from contextforge.providers.embedding import MockEmbeddingProvider
    
    # Adapter to use library mock with app interface
    class MockEmbeddingClientAdapter(EmbeddingClient):
        def __init__(self):
            self._provider = MockEmbeddingProvider()
        
        async def embed(self, text: str) -> list[float]:
            return await self._provider.embed(text)
        
        async def embed_batch(self, texts: list[str]) -> list[list[float]]:
            return await self._provider.embed_batch(texts)
    
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/contextforge")
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    embedding_client = MockEmbeddingClientAdapter()
    
    async with async_session() as session:
        print("=" * 70)
        print("ContextForge Hybrid Search Test")
        print("=" * 70)
        
        for i, test in enumerate(TEST_CASES, 1):
            print(f"\n--- Test {i}: {test['description']} ---")
            print(f"Query: '{test['query']}'")
            print(f"Node Types: {test['node_types']}")
            
            # Generate query embedding
            query_embedding = await embedding_client.embed(test['query'])
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            
            # Run hybrid search
            try:
                result = await session.execute(
                    text("""
                        SELECT * FROM hybrid_search_nodes(
                            :query_text,
                            :query_embedding::vector,
                            :tenant_ids,
                            :node_types,
                            :top_k,
                            :bm25_weight,
                            :vector_weight
                        )
                    """),
                    {
                        "query_text": test['query'],
                        "query_embedding": embedding_str,
                        "tenant_ids": ["demo"],
                        "node_types": test['node_types'],
                        "top_k": 5,
                        "bm25_weight": 0.4,
                        "vector_weight": 0.6,
                    }
                )
                
                rows = result.fetchall()
                
                print(f"\nResults ({len(rows)} found):")
                print("-" * 60)
                print(f"{'Node ID':<10} {'BM25':<10} {'Vector':<10} {'Combined':<10}")
                print("-" * 60)
                
                for row in rows:
                    node_id, bm25_score, vector_score, combined_score = row
                    print(f"{node_id:<10} {bm25_score:<10.4f} {vector_score:<10.4f} {combined_score:<10.4f}")
                
                # Score interpretation
                if rows:
                    top_score = rows[0][3]
                    if top_score >= 0.85:
                        interpretation = "HIGH CONFIDENCE - Use directly"
                    elif top_score >= 0.70:
                        interpretation = "GOOD MATCH - Include in results"
                    elif top_score >= 0.50:
                        interpretation = "PARTIAL MATCH - Review before using"
                    else:
                        interpretation = "LOW CONFIDENCE - Consider excluding"
                    print(f"\nTop Score Interpretation: {interpretation}")
                    
            except Exception as e:
                print(f"Error: {e}")
                print("Note: Make sure hybrid_search_nodes function exists and data is populated")
        
        # Test weight comparison
        print("\n" + "=" * 70)
        print("Weight Comparison Test")
        print("=" * 70)
        
        test_query = "pending orders"
        query_embedding = await embedding_client.embed(test_query)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        
        weights = [
            (0.4, 0.6, "Default (40% BM25, 60% Vector)"),
            (0.6, 0.4, "Keyword Heavy (60% BM25, 40% Vector)"),
            (0.2, 0.8, "Semantic Heavy (20% BM25, 80% Vector)"),
        ]
        
        for bm25_w, vec_w, description in weights:
            print(f"\n{description}:")
            try:
                result = await session.execute(
                    text("""
                        SELECT * FROM hybrid_search_nodes(
                            :query_text, :query_embedding::vector,
                            :tenant_ids, :node_types, :top_k,
                            :bm25_weight, :vector_weight
                        ) LIMIT 3
                    """),
                    {
                        "query_text": test_query,
                        "query_embedding": embedding_str,
                        "tenant_ids": ["demo"],
                        "node_types": ["schema_field"],
                        "top_k": 3,
                        "bm25_weight": bm25_w,
                        "vector_weight": vec_w,
                    }
                )
                rows = result.fetchall()
                for row in rows:
                    print(f"  Node {row[0]}: BM25={row[1]:.4f}, Vec={row[2]:.4f}, Combined={row[3]:.4f}")
            except Exception as e:
                print(f"  Error: {e}")
        
        print("\n" + "=" * 70)
        print("Test Complete!")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
