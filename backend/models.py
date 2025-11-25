from pydantic import BaseModel

class IngestRequest(BaseModel):
    doc_id: str
    text: str

class AskRequest(BaseModel):
    question: str
    top_k: int = 4    

class ChatStoreRequest(BaseModel):
    chat: str    