import re
import os
import httpx
import asyncio
from typing import List
from dotenv import load_dotenv
from pypdf import PdfReader
import io
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ------------------------------------------------------------
# OPTIONAL: Turn refinement ON/OFF to avoid slow ingestion
# ------------------------------------------------------------
REFINE_WITH_LLM = False   # ← Turn ON when needed
# ------------------------------------------------------------
def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().split(".")[-1]

    # PDF case
    if ext == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    # TXT, MD etc
    return file_bytes.decode("utf-8", errors="ignore")

# ---------------------- ASYNC LLM REFINER ----------------------
async def refine_chunk_with_llm_async(chunk: str) -> str:
    """
    Refine text using Gemini. (ASYNC)
    Safe: Returns original chunk if LLM fails.
    """

    prompt = f"""
You are a text normalization engine for a RAG system.

Rewrite the text to:
- remain meaningful,
- stay accurate,
- remove noise,
- improve clarity + structure,
- optimize for embedding retrieval.

Text:
\"\"\"{chunk}\"\"\"
    """

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(url, json=payload, params={"key": GEMINI_API_KEY})
            data = res.json()

        refined = data["candidates"][0]["content"]["parts"][0]["text"]
        return refined.strip()

    except Exception as e:
        print("⚠️ Gemini refinement failed:", e)
        return chunk  # fallback safe


# ---------------------- SYNC WRAPPER ----------------------
def refine_chunk_with_llm(chunk: str) -> str:
    """
    Sync wrapper for the async LLM refinement.
    """
    return asyncio.run(refine_chunk_with_llm_async(chunk))


# ---------------------- CHUNKER ----------------------
def chunk_text(text: str, chunk_size_chars: int = 1000, overlap: int = 200) -> List[str]:
    """
    Clean + chunk text.
    Optionally refine using LLM.
    Always returns normal Python list of strings.
    """

    text = re.sub(r"\s+", " ", text).strip()
    start = 0
    chunks = []
    L = len(text)

    while start < L:
        end = start + chunk_size_chars
        chunk = text[start:end]

        if REFINE_WITH_LLM:
            refined = refine_chunk_with_llm(chunk)  # safe sync wrapper
            chunks.append(refined)
        else:
            chunks.append(chunk)

        start = end - overlap
        if start < 0:
            start = 0

    return chunks


# ---------------------- PROMPT BUILDER ----------------------
def build_prompt(query: str, retrieved_chunks):
    """
    Build context-aware RAG prompt.
    """

    ctx = "\n\n".join(
        [f"Source [{r.get('id', i)}]: {r['document']}" for i, r in enumerate(retrieved_chunks)]
    )

    prompt = f"""
You are an intelligent, helpful assistant.

Use ONLY the context below. If the answer is not present in the context,
respond with: "I don't know".

---------------------
CONTEXT:
{ctx}
---------------------

USER QUESTION:
{query}

Provide a clear, human-friendly, concise answer.
"""
    return prompt


