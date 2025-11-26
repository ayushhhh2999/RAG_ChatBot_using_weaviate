import os
import httpx
from dotenv import load_dotenv

load_dotenv()

JINA_API_KEY = os.getenv("JINA_API_KEY")

if not JINA_API_KEY:
    raise RuntimeError("❌ Missing JINA_API_KEY")

JINA_URL = "https://api.jina.ai/v1/embeddings"

headers = {
    "Authorization": f"Bearer {JINA_API_KEY}",
    "Content-Type": "application/json"
}

def jina_embed(text: str):
    """
    Returns vector: list[float]  (guaranteed)
    Throws clear errors if anything goes wrong.
    """

    payload = {
        "model": "jina-embeddings-v3",
        "input": text
    }

    try:
        r = httpx.post(JINA_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()

        # Jina returns:
        # { "data": [ { "embedding": [...] } ] }
        vector = data["data"][0]["embedding"]

        if not isinstance(vector, list):
            raise ValueError("embedding is not a list")

        return vector

    except Exception as e:
        print("❌ Jina embed failed:", e)
        return []  # avoid crashing ingestion
