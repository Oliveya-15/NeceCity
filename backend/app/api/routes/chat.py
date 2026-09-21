from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.city import City
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import get_chat_reply

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    city = db.get(City, payload.city_id)
    if city is None:
        raise HTTPException(status_code=404, detail=f"City {payload.city_id} not found.")

    if not payload.message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty.")

    reply, mode = get_chat_reply(db, city, payload.message, payload.history)
    return ChatResponse(reply=reply, mode=mode)
