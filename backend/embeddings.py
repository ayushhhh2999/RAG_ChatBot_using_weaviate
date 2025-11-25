# embeddings.py
import os
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

JINA_API_KEY = os.getenv("JINA_API_KEY")
if not JINA_API_KEY:
    raise RuntimeError("❌ JINA_API_KEY not set in .env")


def jina_embed(text: str) -> np.ndarray:
    """Get embeddings from Jina API using REST."""
    url = "https://api.jina.ai/v1/embeddings"

    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "jina-embeddings-v2-base-en",
        "input": [text]  # ✅ MUST be a list
    }

    response = requests.post(url, json=payload, headers=headers, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(f"Jina API Error: {response.text}")

    embedding = response.json()["data"][0]["embedding"]
    return np.array(embedding, dtype="float32")
