# main.py
import os
import json
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

# NEW GROQ CLIENT (Responses API)
from openai import OpenAI

# Utils + DB
from embeddings import jina_embed
from db import (
    add_chunk,
    query_embeddings,
    clean_messed_up_data,
    find_corrupted_chunks,
    keyword_search,
    hybrid_search,
    delete_similar_to_prompt
)
from db import client, COLLECTION_NAME
from utils import chunk_text, build_prompt, extract_text_from_file
from models import IngestRequest, AskRequest, ChatStoreRequest, DeleteSimilarRequest


# ======================================================
# LOAD ENV + GROQ SETUP
# ======================================================
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("❌ Missing GROQ_API_KEY in environment variables")

groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)


# ======================================================
# GROQ RESPONSE HELPER
# ======================================================
def groq_generate(prompt: str) -> str:
    """
    Generate output using Groq's new Responses API.
    """
    try:
        resp = groq_client.responses.create(
            model="llama-3.3-70b-versatile",
            input=prompt
        )
        return resp.output_text
    except Exception as e:
        return f"⚠️ Groq generation error: {str(e)}"


# ======================================================
# FASTAPI APP
# ======================================================
app = FastAPI(title="Personal AI Agent (Weaviate + Jina + Groq)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================================
# INGEST ENDPOINT
# ======================================================
@app.post("/ingest")
async def ingest(
    doc_id: str = Form(...),
    file: UploadFile = File(None),
    text: str = Form(None)
):
    """
    Extract → Chunk → Embed → Store in Weaviate
    """
    # 1) Extract text
    if file and file.filename:
        raw = await file.read()
        content = extract_text_from_file(raw, file.filename)
        if not content.strip():
            return {"error": "Unable to extract meaningful text from file"}
    elif text:
        content = text.strip()
    else:
        return {"error": "Provide either file or text"}

    # 2) Chunk
    chunks = chunk_text(content, 1200, 200)

    # 3) Embed & store
    added = 0
    for ch in chunks:
        emb = jina_embed(ch)
        add_chunk(doc_id, ch, emb)
        added += 1

    return {"status": "ok", "doc_id": doc_id, "chunks_added": added}


# ======================================================
# RAG: Ranking Helper
# ======================================================
def safe(x):
    try:
        return float(x or 0)
    except:
        return 0.0


def merge_and_rank(vec, bm25, hybrid, top_k=6):
    combined = {}

    # VECTOR RESULTS
    for r in vec:
        key = r["chunk"]
        sim = 1 / (1 + safe(r.get("distance")))
        combined[key] = {
            "chunk": r["chunk"],
            "doc_id": r["doc_id"],
            "vector_score": sim,
            "bm25_score": 0.0,
            "hybrid_score": 0.0,
        }

    # BM25
    for r in bm25:
        key = r["chunk"]
        sc = safe(r.get("score"))
        combined.setdefault(key, {
            "chunk": r["chunk"],
            "doc_id": r["doc_id"],
            "vector_score": 0,
            "bm25_score": 0,
            "hybrid_score": 0,
        })["bm25_score"] += sc

    # HYBRID
    for r in hybrid:
        key = r["chunk"]
        sc = safe(r.get("score"))
        combined.setdefault(key, {
            "chunk": r["chunk"],
            "doc_id": r["doc_id"],
            "vector_score": 0,
            "bm25_score": 0,
            "hybrid_score": 0,
        })["hybrid_score"] += sc

    # FINAL RANKING
    ranked = []
    for d in combined.values():
        final = (
            0.5 * d["vector_score"] +
            0.3 * d["bm25_score"] +
            0.2 * d["hybrid_score"]
        )
        ranked.append({**d, "score": final})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]


# ======================================================
# ASK ENDPOINT
# ======================================================
@app.post("/ask")
async def ask(req: AskRequest):
    q_emb = jina_embed(req.question)

    vec = query_embeddings(q_emb, req.top_k)
    bm25 = keyword_search(req.question, req.top_k)
    hybrid = hybrid_search(req.question, q_emb, req.top_k)

    best = merge_and_rank(vec, bm25, hybrid, top_k=6)

    if not best:
        return {"answer": "No relevant information found.", "sources": []}

    docs = [
        {"id": d["doc_id"], "document": d["chunk"], "score": d["score"]}
        for d in best
    ]

    final_prompt = build_prompt(req.question, docs)
    final_prompt += "\nSpeak in a warm personal tone. Address Ayush directly."

    answer = groq_generate(final_prompt)

    return {"answer": answer, "sources": [d["id"] for d in docs]}

from logging import getLogger
logger = getLogger(__name__)
# ======================================================
# CHAT MEMORY CLASSIFIER
# ======================================================
@app.post("/chat")
async def chat_analyze(req: ChatStoreRequest):
    user_text = req.chat.strip()
    user_text_lower = user_text.lower()

    # --- HARD FILTER (instant reject obvious noise) ---
    NON_MEMORY_KEYWORDS = {
        "hi", "hello", "hey", "yo", "sup", "wassup", "heyy", "hiii",
        "thanks", "thank you", "ty", "thx", "ok", "okay", "k", "kk",
        "lol", "lmao", "haha", "hehe", "nice", "cool", "great",
        "yes", "no", "yep", "nope", "sure", "alright", "got it",
        "continue", "go on", "next", "hmm", "hmmm", "brb", "gn", "good night"
    }

    if len(user_text) < 6 or user_text_lower in NON_MEMORY_KEYWORDS:
        return {"flag": False, "reason": "hard-filter"}

    if user_text_lower.startswith(("i'm ", "im ")) and any(
        phrase in user_text_lower for phrase in [
            "i'm tired", "i'm sleepy", "i'm hungry", "i'm eating",
            "i'm going to", "i'm heading", "i'm about to", "i'm watching",
            "i'm playing", "i'm working", "i'm studying", "i'm busy"
        ]
    ):
        return {"flag": False, "reason": "transient_state"}

    # --- ULTRA-ROBUST RAG-STYLE PROMPT (2025 best practice) ---
    prompt = f"""You are a highly precise personal memory classifier for a long-term memory system.
Your only job is to detect if the user's message reveals persistent, identity-defining, or long-term useful information about themselves.

USER MESSAGE (exact):
\"\"\"
{user_text}
\"\"\"

INSTRUCTIONS — FOLLOW EXACTLY:

1. STORE ONLY if the message reveals stable, long-term personal facts such as:
   • Name, age, location, job, education, family
   • Strong preferences (favorite food, music genre, hobbies, allergies, values)
   • Routines and habits (sleep schedule, workout routine, diet, daily rituals)
   • Life goals, fears, dreams, beliefs, personality traits
   • Important ongoing contexts (job hunting, learning a skill, health conditions)

2. REJECT everything else, especially:
   • Temporary states ("I'm tired right now", "eating pizza")
   • Casual chit-chat, greetings, laughter, acknowledgments
   • Commands or questions without personal revelation
   • Vague or generic statements ("I like coding" → reject unless specific and repeated)

3. Output STRICTLY valid JSON only. No explanations. No markdown.

VALID JSON FORMAT:
{{
  "store": true|false,
  "title": "One-line memory title (8 words max)",
  "memory": "Clean, neutral, permanent fact only — no quotes, no fluff"
}}

EXAMPLES:

Input: "Hey, just wanted to say hi!"
→ {{"store": false}}

Input: "My name is Sarah and I’m a 28-year-old designer from Berlin"
→ {{"store": true, "title": "User name and background", "memory": "Name is Sarah, 28 years old, designer living in Berlin"}}

Input: "I always drink coffee at least 3 liters of water a day"
→ {{"store": true, "title": "Daily water intake habit", "memory": "Drinks minimum 3 liters of water daily"}}

Input: "Haha yeah that’s funny"
→ {{"store": false}}

Now classify the user message above.
"""

    # --- LLM classification ---
    raw = groq_generate(prompt)
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(cleaned)
        if not isinstance(result, dict):
            raise ValueError("Not a dict")
    except Exception as e:
        logger.warning(f"Memory classifier failed to parse JSON: {raw[:200]} | Error: {e}")
        return {"flag": False, "reason": "llm_json_parse_failed", "raw": raw}

    # --- FINAL SAFETY GUARDRAILS ---
    if not result.get("store", False):
        return {"flag": False, "reason": "llm_rejected"}

    title = str(result.get("title", "")).strip()
    memory = str(result.get("memory", "")).strip()

    if not memory or len(memory.split()) < 4:
        return {"flag": False, "reason": "memory_too_short"}

    if any(greeting in memory.lower() for greeting in ["hi ", "hello", "hey ", "thanks"]):
        return {"flag": False, "reason": "greeting_in_memory"}

    if len(memory) > 800:  # prevent huge junk
        return {"flag": False, "reason": "memory_too_long"}

    # --- Store memory ---
    chunks = chunk_text(memory, 1200, 200)
    stored = 0

    for chunk in chunks:
        emb = jina_embed(chunk)
        add_chunk(
            doc_id=title or "Personal Memory",
            chunk=chunk,
            embedding=emb,
        )
        stored += 1

    return {
        "flag": True,
        "title": title,
        "information": memory,
        "original_message": user_text,
        "stored_chunks": stored
    }

# ======================================================
# UTIL ENDPOINTS
# ======================================================
@app.delete("/clean-database")
async def clean_db():
    r = clean_messed_up_data()
    return {"deleted": r["cleaned"]}


@app.get("/documents")
async def list_docs():
    col = client.collections.get(COLLECTION_NAME)
    objs = col.query.fetch_objects(limit=200)
    return {"total_chunks": len(objs.objects)}


@app.get("/find_corrupted-chunks")
async def corrupted():
    return {
        "corrupted_count": len(find_corrupted_chunks()),
        "items": find_corrupted_chunks(),
    }


@app.delete("/delete_similar_chunks")
async def delete_similar(req: DeleteSimilarRequest):
    res = delete_similar_to_prompt(req)
    return {"status": "ok", "deleted_chunks": res}


# ======================================================
# RUN
# ======================================================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
