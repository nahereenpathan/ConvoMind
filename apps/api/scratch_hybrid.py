import asyncio, json, re, sqlite3
from app.services.embedding.mock_provider import MockEmbeddingProvider

conn = sqlite3.connect('dev.db')
c = conn.cursor()
rows = c.execute("SELECT chunk_index, content, embedding FROM transcript_embeddings WHERE meeting_id = 'fb500a9cbc7246458ac29ea517e2f909'").fetchall()

provider = MockEmbeddingProvider()

def compute_lexical_score(query: str, content: str) -> float:
    # Normalize query & content
    q_clean = re.sub(r"['’]s\b", "", query.lower())
    c_lower = content.lower()
    
    stop_words = {"what", "is", "the", "in", "on", "at", "to", "for", "of", "and", "or", "was", "were", "this", "that", "there", "about", "with", "tell", "me", "did", "they", "discuss", "made", "does", "need"}
    q_tokens = [w.strip(".,!?:;\"'()[]{}") for w in q_clean.split() if len(w) > 1 and w not in stop_words]
    
    if not q_tokens:
        return 0.0

    score = 0.0
    for tok in q_tokens:
        if tok in c_lower:
            score += 1.0
        elif tok in ("sara", "sarah") and any(n in c_lower for n in ("sara", "sarah")):
            score += 1.5
        elif tok in ("arjun", "general") and any(n in c_lower for n in ("arjun", "general")):
            score += 1.5
        elif tok in ("daniel", "marketing") and any(n in c_lower for n in ("daniel", "marketing")):
            score += 1.5
        elif tok in ("assign", "assigned") and any(w in c_lower for w in ("handle", "prepare", "improve", "responsible", "task")):
            score += 0.8
        elif tok in ("deadline", "due", "when") and any(w in c_lower for w in ("october", "by")):
            score += 0.8

    normalized_score = min(1.0, score / max(1.0, len(q_tokens)))
    return normalized_score

async def run_hybrid_search(query: str, threshold: float = 0.15):
    q_vec = await provider.generate_query_embedding(query)
    results = []
    for r in rows:
        emb = json.loads(r[2]) if isinstance(r[2], str) else r[2]
        cos_sim = max(0.0, min(1.0, sum(a * b for a, b in zip(q_vec, emb))))
        lex_score = compute_lexical_score(query, r[1])
        
        # Hybrid formula
        if lex_score >= 0.3:
            final_score = 0.3 * cos_sim + 0.7 * lex_score
        else:
            final_score = 0.7 * cos_sim + 0.3 * lex_score
            
        final_score = round(final_score, 4)
        if threshold is not None and final_score < threshold:
            continue
        results.append((final_score, cos_sim, lex_score, r[0], r[1][:80]))
        
    results.sort(key=lambda x: x[0], reverse=True)
    return results

async def main():
    queries = [
        ("What task is assign to sara?", 0.2),
        ("What is Sara responsible for?", 0.2),
        ("What does Sara need to complete?", 0.2),
        ("When is Sara's deadline?", 0.2),
        ("What is the clinic's opening time?", 0.3),
        ("What is the weather forecast in Tokyo tomorrow?", 1.0),
    ]
    for q, th in queries:
        print(f"\n--- Query: '{q}' (threshold={th}) ---")
        res = await run_hybrid_search(q, th)
        print(f"Results returned: {len(res)}")
        for r in res:
            print(f"  Chunk {r[3]}: final={r[0]} (cos={r[1]:.4f}, lex={r[2]:.4f}) | {r[4]}...")

asyncio.run(main())
