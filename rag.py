import chromadb
from sentence_transformers import SentenceTransformer

_client = chromadb.PersistentClient(path="./chroma_db")
_collection = _client.get_or_create_collection("nexus_knowledge")
_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_documents(docs: list[dict]) -> None:
    """Embed and upsert documents into ChromaDB.

    Each doc must have: {"id": str, "text": str, "topic": str}
    """
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    metadatas = [{"topic": d["topic"]} for d in docs]
    embeddings = _model.encode(texts).tolist()
    _collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )


def retrieve_context(query: str, topic: str = None, n: int = 3) -> str:
    """Return top-n relevant chunks for a query, joined as a single string."""
    try:
        count = _collection.count()
        if count == 0:
            return ""
        n_results = min(n, count)
        embedding = _model.encode([query]).tolist()
        kwargs = {"query_embeddings": embedding, "n_results": n_results}
        if topic:
            kwargs["where"] = {"topic": topic}
        results = _collection.query(**kwargs)
        chunks = results.get("documents", [[]])[0]
        return "\n\n".join(chunks)
    except Exception:
        return ""
