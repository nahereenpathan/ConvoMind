import asyncio, json, sqlite3
from app.services.embedding.mock_provider import MockEmbeddingProvider

conn = sqlite3.connect('dev.db')
c = conn.cursor()
rows = c.execute("SELECT chunk_index, content, embedding FROM transcript_embeddings WHERE meeting_id = 'fb500a9cbc7246458ac29ea517e2f909'").fetchall()

provider = MockEmbeddingProvider()

async def test():
    queries = [
        "What task is assign to sara?",
        "What is Sara responsible for?",
        "What does Sara need to complete?",
        "When is Sara's deadline?",
        "What is the clinic's opening time?"
    ]
    for q in queries:
        print(f"\nQuery: {q}")
        q_vec = await provider.generate_query_embedding(q)
        for r in rows:
            emb = json.loads(r[2]) if isinstance(r[2], str) else r[2]
            dot = sum(a * b for a, b in zip(q_vec, emb))
            print(f"  Chunk {r[0]}: cosine similarity = {dot:.4f}")

asyncio.run(test())
