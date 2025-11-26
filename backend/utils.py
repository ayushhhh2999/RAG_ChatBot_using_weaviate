import re
import os
import httpx
import asyncio
from typing import List
from dotenv import load_dotenv
from pypdf import PdfReader
import io

# NEW GROQ CLIENT
from openai import OpenAI

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# ------------------------------------------------------------
# OPTIONAL: Turn refinement ON/OFF
# ------------------------------------------------------------
REFINE_WITH_LLM = False  # Set True only when needed
# ------------------------------------------------------------


# ---------------------- FILE TEXT EXTRACTOR ----------------------
def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().split(".")[-1]

    if ext == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    return file_bytes.decode("utf-8", errors="ignore")


# ---------------------- ASYNC GROQ REFINER ----------------------
async def refine_chunk_with_llm_async(chunk: str) -> str:
    """
    Text refinement using Groq Responses API.
    Falls back to original chunk on ANY error.
    """

    prompt = f"""
You are a text-refinement engine for a Retrieval-Augmented Generation (RAG) system.

Rewrite the text to:
- improve clarity
- remove noise
- remain factual
- enhance semantic quality
- keep meaning intact

TEXT:
\"\"\"{chunk}\"\"\"
    """

    try:
        resp = groq_client.responses.create(
            model="llama-3.3-70b-versatile",
            input=prompt,
            max_output_tokens=512
        )

        return resp.output_text.strip()

    except Exception as e:
        print("⚠️ Groq refinement failed:", e)
        return chunk


# ---------------------- SYNC WRAPPER ----------------------
def refine_chunk_with_llm(chunk: str) -> str:
    """Run async refiner synchronously (FastAPI safe)."""
    return asyncio.run(refine_chunk_with_llm_async(chunk))


# ---------------------- CHUNKER ----------------------
def chunk_text(text: str, chunk_size_chars: int = 1000, overlap: int = 200) -> List[str]:
    """
    Clean + chunk text.
    Optionally refine chunks using Groq LLM.
    """

    text = re.sub(r"\s+", " ", text).strip()
    start = 0
    chunks = []
    L = len(text)

    while start < L:
        end = start + chunk_size_chars
        chunk = text[start:end]

        if REFINE_WITH_LLM:
            refined = refine_chunk_with_llm(chunk)
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
    Build final RAG prompt sent to Groq (Responses API).
    """

    ctx = "\n\n".join(
        [
            f"Source [{idx}] (doc_id: {r.get('id')}):\n{r['document']}"
            for idx, r in enumerate(retrieved_chunks)
        ]
    )

    return f"""
You are an intelligent assistant for a RAG system.

RULES:
- Use ONLY the provided context.
- If the answer is not in the context, reply strictly: "I don't know".
- Be concise and helpful.
- Do NOT hallucinate.

---------------------
CONTEXT:
{ctx}
---------------------

USER QUESTION:
{query}

Provide the most accurate answer using ONLY the context.
"""
