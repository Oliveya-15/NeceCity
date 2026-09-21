from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    city_id: int
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
    mode: str  # "llm" | "rule_based"
