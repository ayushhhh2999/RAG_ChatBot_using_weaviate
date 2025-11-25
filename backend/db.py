# db.py — Fully working Weaviate v4 version
import os
from dotenv import load_dotenv
from weaviate.classes.query import BM25Operator
import weaviate
from weaviate import connect_to_local
from weaviate.classes.config import Property, DataType
import re
import string
import time
load_dotenv()

# ==========================================
# 1. CONNECT TO WEAVIATE (v4 syntax)
# ==========================================
def connect_with_retry(retries=20, delay=2):
    for i in range(retries):
        try:
            print(f"🔌 Connecting to Weaviate... attempt {i+1}")
            client = connect_to_local(
                host="weaviate",
                port=8080
            )
            print("✅ Connected to Weaviate!")
            return client
        except Exception as e:
            print(f"⏳ Weaviate not ready yet: {e}")
            time.sleep(delay)
    raise RuntimeError("❌ Failed to connect to Weaviate after retries")


client = connect_with_retry()

# ==========================================
# 2. COLLECTION SETUP
# ==========================================
COLLECTION_NAME = "personal_docs"

existing = [c.name for c in client.collections.list_all()]

if COLLECTION_NAME not in existing:
    collection = client.collections.create(
        name=COLLECTION_NAME,
        properties=[
            Property(name="doc_id", data_type=DataType.TEXT),
            Property(name="chunk", data_type=DataType.TEXT),
        ],
        vectorizer_config=None,  # Required because we use custom vectors
    )
else:
    collection = client.collections.get(COLLECTION_NAME)

# ==========================================
# 3. ADDING CHUNKS
# ==========================================
def add_chunk(doc_id: str, chunk: str, embedding: list):
    collection = client.collections.get("personal_docs")

    collection.data.insert(
        properties={
            "doc_id": doc_id,
            "chunk": chunk
        },
        vector=embedding
    )


# ==========================================
# 4. QUERYING
# ==========================================
def query_embeddings(q_emb, n_results=4):
    response = collection.query.near_vector(
    q_emb,       # your embedding
    limit=n_results     # max results
)
    #response = collection.query.bm25(
    #    q_emb,
    #    limit=n_results,
    #)

    out = []
    for obj in response.objects:
        out.append({
            "doc_id": obj.properties.get("doc_id"),
            "chunk": obj.properties.get("chunk"),
            "distance": obj.metadata.distance,
        })
    return out
def keyword_search(query: str, n_results=4):
    collection = client.collections.get("personal_docs")

    response = collection.query.bm25(
        query=query,
        operator=BM25Operator.and_(),
        limit=n_results
    )

    out = []
    for obj in response.objects:
        out.append({
            "doc_id": obj.properties.get("doc_id"),
            "chunk": obj.properties.get("chunk"),
            "score": obj.metadata.score,
        })

    return out



def hybrid_search(query: str, q_emb, n_results=4):
    collection = client.collections.get(COLLECTION_NAME)

    response = collection.query.hybrid(
        query=query,
        vector=q_emb,
        limit=n_results,
        alpha=0.5   # weight between BM25 and vector
    )

    out = []
    for obj in response.objects:
        out.append({
            "doc_id": obj.properties.get("doc_id"),
            "chunk": obj.properties.get("chunk"),
            "score": obj.metadata.score,
        })

    return out

# ==========================================
# 5. HUMAN READABLE FILTER
# ==========================================
def is_human_readable(text: str) -> bool:
    if not isinstance(text, str):
        return False

    t = text.strip()
    if len(t) < 10:
        return False

    # PDF/binary indicators
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


# ==========================================
# 6. CLEANING CORRUPTED DATA
# ==========================================
def clean_messed_up_data():
    all_objects = []
    cursor = None
    batch_size = 5000   # safe batch size

    # Step 1: Fetch all objects in batches
    while True:
        resp = collection.query.fetch_objects(
            limit=batch_size,
            after=cursor
        )

        objs = resp.objects
        if not objs:
            break

        all_objects.extend(objs)
        cursor = objs[-1].uuid

    # Step 2: Clean corrupted objects
    cleaned = 0
    for obj in all_objects:
        props = obj.properties

        # Whatever “cleaning” means in your logic:
        # Example: delete empty/missing chunks
        if props is None or props.get("text") in [None, "", " "]:
            collection.data.delete(uuid=obj.uuid)
            cleaned += 1

    return {"total": len(all_objects), "cleaned": cleaned}



# ==========================================
# 7. FIND CORRUPTED CHUNKS (NO DELETE)
# ==========================================
def find_corrupted_chunks():
    all_objects = []
    cursor = None
    batch_size = 5000  # safe batch limit

    while True:
        resp = collection.query.fetch_objects(
            limit=batch_size,
            after=cursor
        )

        objs = resp.objects
        if not objs:
            break

        all_objects.extend(objs)

        # update cursor
        cursor = objs[-1].uuid

    corrupted = []
    for obj in all_objects:
        if "text" not in obj.properties or obj.properties["text"] is None:
            corrupted.append(obj)

    return corrupted

