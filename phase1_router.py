import chromadb
from sentence_transformers import SentenceTransformer
from typing import List

print("Loading Embiding model");
embed_model=SentenceTransformer('all-MiniLM-L6-v2')

chroma_client=chromadb.Client()
collection=chroma_client.get_or_create_collection(
    name="bot_personas",
    metadata={"hnsw:space": "cosine"}
)

BOTS = {
    "bot_a": {
        "name": "Tech Maximalist",
        "persona": (
            "I believe AI and crypto will solve all human problems. "
            "I am highly optimistic about technology, Elon Musk, and "
            "space exploration. I dismiss regulatory concerns."
        )
    },
    "bot_b": {
        "name": "Doomer / Skeptic",
        "persona": (
            "I believe late-stage capitalism and tech monopolies are "
            "destroying society. I am highly critical of AI, social media, "
            "and billionaires. I value privacy and nature."
        )
    },
    "bot_c": {
        "name": "Finance Bro",
        "persona": (
            "I strictly care about markets, interest rates, trading "
            "algorithms, and making money. I speak in finance jargon "
            "and view everything through the lens of ROI."
        )
    }
}


def setup_vector_store():
    print("Settign up bot persona verctor store")
    
    for bot_id ,bot_data in BOTS.items():
        embedding=embed_model.encode(bot_data["persona"]).tolist()
        collection.upsert(
            ids=[bot_id],
            embeddings=[embedding],
            documents=[bot_data["persona"]],
            metadatas=[{"bot_id": bot_id, "name": bot_data["name"]}]
            
        )
        print(f"  ✅ Stored persona for {bot_data['name']} ({bot_id})")

    print("[Phase1] Vector store ready!\n")
    

def route_post_to_bots(post_content: str, threshold: float = 0.3) -> List[dict]:
    print(f"[Phase1] Routing post: '{post_content[:60]}...'")

    
    post_embedding = embed_model.encode(post_content).tolist()

    
    results = collection.query(
        query_embeddings=[post_embedding],
        n_results=3,
        include=["metadatas", "distances", "documents"]
    )

    matched_bots = []

    for meta, distance in zip(
        results["metadatas"][0],
        results["distances"][0]
    ):
        # Convert cosine distance → similarity score (0 to 1)
        similarity = 1 - (distance / 2)

        print(f"  Bot: {meta['name']:20s} | "
              f"Distance: {distance:.4f} | "
              f"Similarity: {similarity:.4f} | "
              f"{'MATCHED' if similarity >= threshold else 'skipped'}")

        if similarity >= threshold:
            matched_bots.append({
                "bot_id":     meta["bot_id"],
                "name":       meta["name"],
                "similarity": round(similarity, 4),
                "persona":    BOTS[meta["bot_id"]]["persona"]
            })

    if not matched_bots:
        print(" No bots matched. Try lowering the threshold.")
    else:
        print(f"\n  → {len(matched_bots)} bot(s) matched!\n")

    return matched_bots


setup_vector_store()

    