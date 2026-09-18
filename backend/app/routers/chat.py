from fastapi import APIRouter
from pydantic import BaseModel

from app.services import llm

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    system: str | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
def send_chat(request: ChatRequest) -> ChatResponse:
    reply = llm.chat(
        messages=[m.model_dump() for m in request.messages],
        system=request.system,
    )
    return ChatResponse(reply=reply)
