# main.py
import os
import json
import io
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

# Gemini
import google.generativeai as genai

# Utils + DB
from embeddings import jina_embed
from db import (
    add_chunk,
    query_embeddings,
    collection,
    clean_messed_up_data,
    find_corrupted_chunks,
    keyword_search,
    hybrid_search,
)
from utils import chunk_text, build_prompt, extract_text_from_file
from models import IngestRequest, AskRequest, ChatStoreRequest


# ======================================================
# LOAD ENV + GEMINI SETUP
# ======================================================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY missing from environment")

genai.configure(api_key=GEMINI_API_KEY)


# ======================================================
# FASTAPI SETUP
# ======================================================
app = FastAPI(title="Personal AI Agent Backend (Weaviate + Jina + Gemini)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================================
# HELPERS
# ======================================================

def gemini_generate(prompt: str) -> str:
    """Generate output using Gemini with consistent error handling."""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"⚠️ Gemini generation error: {str(e)}"


# ======================================================
# INGEST ENDPOINT
# ======================================================
@app.post("/ingest")
async def ingest(
    doc_id: str = Form(...),
    file: UploadFile = File(None),
    text: str = Form(None),
):
    """
    Extract → Chunk → Embed (Jina) → Store in Weaviate
    """
    # ---------------------------------------
    # 1. Read content
    # ---------------------------------------
    if file and file.filename:
        try:
            raw = await file.read()
            content = extract_text_from_file(raw, file.filename)
        except Exception:
            return {"error": "Failed to extract text from uploaded file"}

        if not content.strip():
            return {"error": "Unable to extract usable text from file"}
    elif text:
        content = text.strip()
    else:
        return {"error": "Provide either 'file' or 'text'."}

    # ---------------------------------------
    # 2. Chunk text
    # ---------------------------------------
    chunks = chunk_text(content, chunk_size_chars=1200, overlap=200)

    # ---------------------------------------
    # 3. Embed + store
    # ---------------------------------------
    added = 0
    for i, chunk in enumerate(chunks):
        print(f"[DEBUG] Embedding chunk {i+1}/{len(chunks)}")

        emb = jina_embed(chunk)
        add_chunk(doc_id=doc_id, chunk=chunk, embedding=emb)
        added += 1

    return {
        "status": "ok",
        "doc_id": doc_id,
        "chunks_added": added,
    }


# ======================================================
# ASK ENDPOINT (RAG)
# ======================================================
def safe(value):
    try:
        if value is None:
            return 0.0
        return float(value)
    except:
        return 0.0


def merge_and_rank(vec, bm25, hybrid, top_k=6):
    combined = {}

    # --------------------------
    # VECTOR RESULTS (distance → score)
    # --------------------------
    for r in vec:
        key = r["chunk"]
        vector_score = safe(1 / (1 + safe(r.get("distance"))))
        combined[key] = {
            "chunk": r["chunk"],
            "doc_id": r["doc_id"],
            "vector_score": vector_score,
            "bm25_score": 0.0,
            "hybrid_score": 0.0,
        }

    # --------------------------
    # BM25 RESULTS (metadata.score)
    # --------------------------
    for r in bm25:
        key = r["chunk"]
        bm25_s = safe(r.get("score") or r.get("bm25_score"))  # works for all formats

        if key not in combined:
            combined[key] = {
                "chunk": r["chunk"],
                "doc_id": r["doc_id"],
                "vector_score": 0.0,
                "bm25_score": bm25_s,
                "hybrid_score": 0.0,
            }
        else:
            combined[key]["bm25_score"] += bm25_s

    # --------------------------
    # HYBRID RESULTS
    # hybrid uses metadata.score
    # --------------------------
    for r in hybrid:
        key = r["chunk"]
        hybrid_s = safe(r.get("score") or r.get("hybrid_score"))

        if key not in combined:
            combined[key] = {
                "chunk": r["chunk"],
                "doc_id": r["doc_id"],
                "vector_score": 0.0,
                "bm25_score": 0.0,
                "hybrid_score": hybrid_s,
            }
        else:
            combined[key]["hybrid_score"] += hybrid_s

    # --------------------------
    # FINAL SCORE WEIGHTING
    # --------------------------
    ranked = []
    for k, v in combined.items():
        final_score = (
            0.5 * safe(v["vector_score"])
            + 0.3 * safe(v["bm25_score"])
            + 0.2 * safe(v["hybrid_score"])
        )
        ranked.append({**v, "score": final_score})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]


@app.post("/ask")
async def ask(req: AskRequest):
    q_emb = jina_embed(req.question)

    # Get candidates from 3 modes
    vec_results = query_embeddings(q_emb, n_results=req.top_k)
    bm25_results = keyword_search(req.question, n_results=req.top_k)
    hybrid_results = hybrid_search(req.question, q_emb, n_results=req.top_k)

    # Merge & select best 6
    best_docs = merge_and_rank(vec_results, bm25_results, hybrid_results, top_k=6)

    if len(best_docs) == 0:
        return {
            "answer": "I couldn't find relevant information. Try rephrasing.",
            "sources": [],
        }

    # Build docs for prompt
    docs = [
        {
            "id": d["doc_id"],
            "document": d["chunk"],
            "score": d["score"]
        }
        for d in best_docs
    ]

    # Build final prompt
    prompt = build_prompt(req.question, docs)
    prompt += """
Speak in a warm, personal, friendly tone.
Talk to Ayush directly. Avoid robotic style.
"""

    answer = gemini_generate(prompt)

    return {
        "answer": answer,
        "sources": [d["id"] for d in docs],
    }

# ======================================================
# CHAT MEMORY CLASSIFIER
# ======================================================
@app.post("/chat")
async def chat_analyze(req: ChatStoreRequest):
    """
    LLM decides whether a message should be saved
    into long-term memory.
    """
    prompt = f"""
You classify whether to store this text in long-term memory.

TEXT:
"{req.chat}"

Rules:
- If it's greetings or chit-chat → flag=false.
- If it contains preference, personal detail, plan, idea, or useful info → flag=true.
- If flag=true: return SHORT title + short cleaned information.

Respond ONLY in JSON:
{{
  "flag": true/false,
  "title": "...",
  "information": "..."
}}
"""

    raw = gemini_generate(prompt)

    # Clean markdown code fences
    def clean_json(text):
        text = text.strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        return text

    cleaned = clean_json(raw)

    try:
        result = json.loads(cleaned)
    except:
        return {"error": "Invalid JSON from LLM", "raw": raw, "cleaned": cleaned}

    if not result.get("flag"):
        return {"flag": False, "title": None, "information": None}

    title = result["title"]
    info = result["information"]

    # Chunk + store memory
    chunks = chunk_text(info, chunk_size_chars=1200, overlap=200)

    stored = 0
    for ch in chunks:
        emb = jina_embed(ch)
        add_chunk(title, ch, emb)
        stored += 1

    return {
        "flag": True,
        "title": title,
        "information": info,
        "stored_chunks": stored,
    }


# ======================================================
# MISC ENDPOINTS
# ======================================================
@app.delete("/clean-database")
async def clean_db():
    result = clean_messed_up_data()
    return {"status": "ok", "deleted": result["deleted"]}


@app.get("/documents")
async def list_docs():
    objs = collection.query.fetch_objects(limit=100)
    return {
        "total_chunks" : len(objs.objects),
        "ids_preview": [o.uuid for o in objs.objects],
    }


@app.get("/find_corrupted-chunks")
async def find_corrupted_chunks_endpoint():
    corrupted = find_corrupted_chunks()
    return {
        "corrupted_count": len(corrupted),
        "corrupted_ids": corrupted,
    }


# ======================================================
# RUN SERVER
# ======================================================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
