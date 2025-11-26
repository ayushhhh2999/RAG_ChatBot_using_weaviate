
#---------------- connect with retry ---------------
# # db.py — clean & stable Weaviate v4 helper module
import os
import time
import re
import string
from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv()

from weaviate import connect_to_local
from weaviate.classes.config import Property, DataType
from weaviate.classes.query import BM25Operator

# your embedding function
from embeddings import jina_embed

# ---------------- CONFIG ----------------
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "weaviate")
WEAVIATE_PORT = int(os.getenv("WEAVIATE_PORT", 8080))
WEAVIATE_GRPC_PORT = int(os.getenv("WEAVIATE_GRPC_PORT", 50051))

COLLECTION_NAME = os.getenv("WEAVIATE_COLLECTION", "Personal_docs")
_FETCH_BATCH_SIZE = 2000


# ----------------------------------------------------
# 🟦 CONNECT WITH RETRIES
# ----------------------------------------------------
def connect_with_retry(retries: int = 20, delay: float = 2.0):
    last_exc = None
    for i in range(retries):
        try:
            print(f"🔌 Connecting to Weaviate... attempt {i+1}")
            client = connect_to_local(
                host=WEAVIATE_HOST,
                port=WEAVIATE_PORT,
                grpc_port=WEAVIATE_GRPC_PORT,
            )
            print("✅ Connected to Weaviate!")
            return client
        except Exception as e:
            last_exc = e
            print(f"⏳ Weaviate not ready yet (attempt {i+1}): {e}")
            time.sleep(delay)

    raise RuntimeError("❌ Failed to connect to Weaviate") from last_exc


client = connect_with_retry()


# ----------------------------------------------------
# 🟦 UNIVERSAL RESPONSE OBJECT EXTRACTOR
# ----------------------------------------------------
def extract_objects(resp):
    """
    Normalizes Weaviate client response formats:

    - New v4 client: resp.objects (QueryReturn)
    - Old client: dict with "objects" key
    """
    if hasattr(resp, "objects") and resp.objects is not None:
        return resp.objects

    if isinstance(resp, dict) and "objects" in resp:
        return resp["objects"]

    return []


# ----------------------------------------------------
# 🟦 ENSURE COLLECTION EXISTS
# ----------------------------------------------------
def ensure_collection():
    global collection

    print("🔍 Checking existing Weaviate collections…")

    try:
        existing = client.collections.list_all()
        print("🔥 RAW list_all():", existing)

        names = []

        # Handle dict
        if isinstance(existing, dict):
            # Try all known keys safely
            if "collections" in existing:
                names = [item.get("name") or item.get("class") 
                         for item in existing["collections"]]
            elif "classes" in existing:
                names = [item.get("class") or item.get("name") 
                         for item in existing["classes"]]
            elif "result" in existing and "collections" in existing["result"]:
                names = [
                    item.get("name") or item.get("class")
                    for item in existing["result"]["collections"]
                ]
            else:
                print("⚠️ Unknown list_all() format. Defaulting to empty schema.")
                names = []

        # Handle v4 typed response
        elif hasattr(existing, "collections"):
            names = [c.name for c in existing.collections]

        print("📚 Found collections:", names)

        # EXISTS → Connect
        if COLLECTION_NAME in names:
            print(f"📁 Collection '{COLLECTION_NAME}' exists. Connecting...")
            collection = client.collections.get(COLLECTION_NAME)
            return collection

        # CREATE
        print(f"📁 Creating collection '{COLLECTION_NAME}'…")
        client.collections.create(
            name=COLLECTION_NAME,
            vectorizer_config=None,
            properties=[
                Property(name="doc_id", data_type=DataType.TEXT),
                Property(name="chunk", data_type=DataType.TEXT),
            ],
        )
        collection = client.collections.get(COLLECTION_NAME)
        print("✅ Collection created successfully!")
        return collection

    except Exception as e:
        print("❌ ensure_collection failed:", e)
        raise
#### RUN THIS FUNCTION FIRST TIME TO CREATE COLLECTION #### THEN NO NEED TO RUN AGAIN ####    
# ensure_collection()
# ----------------------------------------------------
# 🟦 FETCH ALL OBJECTS
# ----------------------------------------------------
def fetch_all_objects(batch_size: int = _FETCH_BATCH_SIZE):
    all_objs = []
    cursor = None

    while True:
        col = client.collections.get(COLLECTION_NAME)
        resp = col.query.fetch_objects(limit=batch_size, after=cursor)
        objs = extract_objects(resp)

        if not objs:
            break

        all_objs.extend(objs)
        last = objs[-1]

        cursor = getattr(last, "uuid", None) or getattr(last, "id", None)

        if cursor is None:
            break

    return all_objs


# ----------------------------------------------------
# 🟦 ADD CHUNK
# ----------------------------------------------------
def add_chunk(doc_id: str, chunk: str, embedding: List[float]):
    if not isinstance(embedding, (list, tuple)):
        raise ValueError("embedding must be a list/tuple of floats")

    col = client.collections.get(COLLECTION_NAME)

    try:
        col.data.insert(
            properties={"doc_id": doc_id, "chunk": chunk},
            vector=embedding
        )
    except Exception:
        col.data.create(
            properties={"doc_id": doc_id, "chunk": chunk},
            vector=embedding
        )

def safe_get(meta, key, default=None):
    """
    Works for both dict and Weaviate typed metadata objects.
    """
    if meta is None:
        return default

    # If dict
    if isinstance(meta, dict):
        return meta.get(key, default)

    # If object with attribute
    if hasattr(meta, key):
        return getattr(meta, key)

    # If object has dict-like __dict__
    if hasattr(meta, "__dict__") and key in meta.__dict__:
        return meta.__dict__.get(key, default)

    return default

# ----------------------------------------------------
# 🟦 SEMANTIC SEARCH
# ----------------------------------------------------
def query_embeddings(q_emb: List[float], n_results: int = 4):
    col = client.collections.get(COLLECTION_NAME)
    resp = col.query.near_vector(q_emb, limit=n_results, return_metadata=["distance"])

    out = []
    for obj in extract_objects(resp):
        props = obj.properties
        meta = obj.metadata
        out.append({
            "doc_id": props.get("doc_id"),
            "chunk": props.get("chunk"),
            "distance": safe_get(meta,"distance"),
            "uuid": obj.uuid
        })
    return out


# ----------------------------------------------------
# 🟦 KEYWORD SEARCH (BM25)
# ----------------------------------------------------
def keyword_search(query: str, n_results: int = 4):
    col = client.collections.get(COLLECTION_NAME)
    resp = col.query.bm25(
        query=query,
        operator=BM25Operator.and_(),
        limit=n_results,
        return_metadata=["score"]
    )

    out = []
    for obj in extract_objects(resp):
        props = obj.properties
        meta = obj.metadata
        out.append({
            "doc_id": props.get("doc_id"),
            "chunk": props.get("chunk"),
            "score": safe_get(meta,"score"),
            "uuid": obj.uuid
        })
    return out


# ----------------------------------------------------
# 🟦 HYBRID SEARCH
# ----------------------------------------------------
def hybrid_search(query: str, q_emb: List[float], n_results: int = 4):
    col = client.collections.get(COLLECTION_NAME)
    resp = col.query.hybrid(
        query=query,
        vector=q_emb,
        alpha=0.5,
        limit=n_results,
        return_metadata=["score", "distance"]
    )

    out = []
    for obj in extract_objects(resp):
        props = obj.properties
        meta = obj.metadata
        out.append({
            "doc_id": props.get("doc_id"),
            "chunk": props.get("chunk"),
            "score": safe_get(meta,"score"),
            "distance":safe_get(meta,"distance"),
            "uuid": obj.uuid
        })
    return out


# ----------------------------------------------------
# (extra functions unchanged)
# ----------------------------------------------------

# ... your other functions (is_human_readable, delete_similar_to_prompt, etc.)
# They only need replacing the loops with extract_objects().




# ---------------- human readable ----------------
def is_human_readable(text: str) -> bool:
    if not isinstance(text, str):
        return False
    t = text.strip()
    if len(t) < 10:
        return False

    binary_markers = ["endstream", "obj", "xref", "%PDF", "stream"]
    if any(m in t for m in binary_markers):
        return False

    if re.search(r"\\x[0-9A-Fa-f]{2}", t):
        return False

    letters = sum(c.isalpha() for c in t)
    symbols = sum(c in string.punctuation for c in t)
    if letters == 0:
        return False
    if symbols > letters * 2:
        return False

    words = t.split()
    real_words = sum(1 for w in words if re.search(r"[A-Za-z]", w))
    return real_words >= 3


# ---------------- cleaning corrupted ----------------
def clean_messed_up_data() -> Dict[str, int]:
    all_objects = fetch_all_objects(batch_size=_FETCH_BATCH_SIZE)
    cleaned = 0
    for obj in all_objects:
        props = getattr(obj, "properties", None) or obj.get("properties", {})
        # accept both "chunk" and older "text" keys
        text_value = props.get("chunk") or props.get("text") or ""
        if text_value is None or str(text_value).strip() == "":
            # delete
            uid = getattr(obj, "uuid", None) or obj.get("uuid")
            if uid:
                _safe_delete(uid)
                cleaned += 1
    return {"total": len(all_objects), "cleaned": cleaned}


# ---------------- find corrupted (no delete) ----------------
def find_corrupted_chunks() -> List[Dict[str, Any]]:
    items = fetch_all_objects(batch_size=_FETCH_BATCH_SIZE)
    corrupted = []

    for obj in items:
        props = getattr(obj, "properties", None) or obj.get("properties", {})
        chunk = (props.get("chunk") or props.get("text") or "") or ""
        readable = is_human_readable(chunk)

        # extra heuristics
        too_many_symbols = (len(chunk) > 0) and (sum(1 for c in chunk if c in string.punctuation) > len(chunk) * 0.35)
        weird_unicode = any(ord(c) > 50000 for c in chunk) if chunk else False
        repeated_char = len(set(chunk)) <= 3 and len(chunk) > 20
        too_few_words = len(chunk.split()) < 3
        token_noise = any(len(t) > 40 for t in chunk.split())
        mostly_digits = (len(chunk) > 0) and (sum(c.isdigit() for c in chunk) > len(chunk) * 0.5)

        corrupted_flag = not readable or too_many_symbols or weird_unicode or repeated_char or too_few_words or token_noise or mostly_digits

        if corrupted_flag:
            corrupted.append({
                "id": getattr(obj, "uuid", None) or obj.get("uuid"),
                "doc_id": props.get("doc_id"),
                "preview": chunk[:200],
            })

    return corrupted


# ---------------- internal safe delete ----------------
def _safe_delete(uuid: str) -> bool:
    col = client.collections.get(COLLECTION_NAME)
    try:
        # try v4 API
        col.data.delete_by_id(uuid)
        return True
    except Exception:
        try:
            # older API fallback
            col.data.delete(uuid=uuid)
            return True
        except Exception as e:
            print("❌ _safe_delete failed for", uuid, ":", e)
            return False


# ---------------- delete similar to prompt ----------------
def delete_similar_to_prompt(prompt: Any, similarity_threshold: float = 0.75, search_limit: int = 5000) -> Dict[str, Any]:
    """
    Delete objects whose semantic similarity to `prompt` >= similarity_threshold.

    - prompt may be a Pydantic request object with .query or a raw string.
    - similarity_threshold is 0..1 (e.g. 0.75 = 75%)
    """
    prompt_text = prompt.query if hasattr(prompt, "query") else prompt
    if not isinstance(prompt_text, str) or prompt_text.strip() == "":
        raise ValueError("prompt must be a non-empty string")

    # 1) embed prompt (your jina_embed)
    emb = jina_embed(prompt_text)

    # 2) run near_vector search and request distance metadata explicitly
    col = client.collections.get(COLLECTION_NAME)
    try:
        resp = col.query.near_vector(emb, limit=search_limit, return_metadata=["distance"])
    except Exception as e:
        return {"error": "near_vector search failed", "exception": str(e)}

    objs = getattr(resp, "objects", []) or resp.get("objects", [])
    if not objs:
        return {"deleted": 0, "reason": "no search results returned"}

    to_delete = []
    debug = []
    total_checked = 0

    for obj in objs:
        total_checked += 1
        uid = getattr(obj, "uuid", None) or obj.get("uuid")
        props = getattr(obj, "properties", None) or obj.get("properties", {})
        meta = getattr(obj, "metadata", None) or obj.get("metadata", {})
        distance = getattr(meta, "distance", None) or safe_get(meta,"distance"),

        if distance is None:
            debug.append({"id": uid, "reason": "no distance"})
            continue

        # convert distance -> similarity
        try:
            d = float(distance)
        except Exception:
            debug.append({"id": uid, "reason": "bad distance", "raw": distance})
            continue

        if 0.0 <= d <= 1.0:
            sim = 1.0 - d
        else:
            # fallback monotonic mapping for other distance types
            sim = 1.0 / (1.0 + d)

        debug.append({"id": uid, "distance": d, "similarity": sim, "doc_id": props.get("doc_id")})

        if sim >= float(similarity_threshold):
            to_delete.append(uid)

    deleted_ids = []
    failed = []
    for uid in to_delete:
        if not uid:
            continue
        ok = _safe_delete(uid)
        if ok:
            deleted_ids.append(uid)
        else:
            failed.append(uid)

    return {
        "prompt": prompt_text,
        "similarity_threshold": similarity_threshold,
        "search_limit": search_limit,
        "total_searched": total_checked,
        "matched_for_deletion": len(to_delete),
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "failed_deletes": failed,
        "debug_sample": debug[:25],
    }
