import json
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import get_settings
from app.database import Base, engine, get_db
from app.models import ChatSession, Message
from app.schemas import ChatRequest, MessageOut, SessionCreated, UsageOut
from app.rate_limit import enforce_rate_limit
from app.services import stream_completion, estimate_tokens, estimate_cost

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Chat Application", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sessions", response_model=SessionCreated)
def create_session(
    db: Session = Depends(get_db),
    key_fingerprint: str = Depends(require_api_key),
):
    session = ChatSession(id=str(uuid4()), api_key_fingerprint=key_fingerprint)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_owned_session(db: Session, session_id: str, key_fingerprint: str) -> ChatSession:
    session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.api_key_fingerprint == key_fingerprint,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def get_messages(
    session_id: str,
    db: Session = Depends(get_db),
    key_fingerprint: str = Depends(require_api_key),
):
    get_owned_session(db, session_id, key_fingerprint)
    return list(db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at, Message.id)
    ))


@app.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    key_fingerprint: str = Depends(require_api_key),
):
    session = get_owned_session(db, session_id, key_fingerprint)
    db.delete(session)
    db.commit()
    return {"detail": "Session deleted"}


@app.post("/sessions/{session_id}/chat")
def chat(
    session_id: str,
    body: ChatRequest,
    db: Session = Depends(get_db),
    key_fingerprint: str = Depends(require_api_key),
):
    session = get_owned_session(db, session_id, key_fingerprint)
    enforce_rate_limit(db, key_fingerprint)

    user_message = Message(
        session_id=session_id,
        role="user",
        content=body.message,
        tokens=estimate_tokens(body.message),
    )
    db.add(user_message)
    db.commit()

    # Load all persisted history, then apply the sliding window for this LLM call.
    all_messages = list(db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at, Message.id)
    ))
    window = body.max_history_messages or get_settings().max_history_messages
    history = all_messages[-window:]
    prompt = [{"role": m.role, "content": m.content} for m in history]

    def event_stream():
        answer_parts = []
        input_tokens = sum(m.tokens for m in history if m.role == "user")
        output_tokens = 0
        try:
            stream = stream_completion(prompt)
            for chunk in stream:
                if not chunk.choices:
                    if getattr(chunk, "usage", None):
                        input_tokens = chunk.usage.prompt_tokens or input_tokens
                        output_tokens = chunk.usage.completion_tokens or output_tokens
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    answer_parts.append(delta)
                    yield "data: " + json.dumps({"content": delta}) + "\n\n"

            answer = "".join(answer_parts)
            if output_tokens == 0:
                output_tokens = estimate_tokens(answer)
            cost = estimate_cost(input_tokens, output_tokens)

            # Use a fresh DB session inside the streaming generator.
            from app.database import SessionLocal
            with SessionLocal() as write_db:
                current = write_db.get(ChatSession, session_id)
                if current:
                    write_db.add(Message(
                        session_id=session_id, role="assistant", content=answer, tokens=output_tokens
                    ))
                    current.total_input_tokens += input_tokens
                    current.total_output_tokens += output_tokens
                    current.total_cost += cost
                    write_db.commit()

            yield "data: " + json.dumps({
                "done": True,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost": round(cost, 8),
            }) + "\n\n"
        except Exception:
            # Do not expose provider secrets or raw exception details to clients.
            yield "data: " + json.dumps({
                "error": "The AI service is temporarily unavailable. Please try again."
            }) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/usage", response_model=UsageOut)
def usage(
    db: Session = Depends(get_db),
    key_fingerprint: str = Depends(require_api_key),
):
    sessions_query = select(func.count(ChatSession.id)).where(
        ChatSession.api_key_fingerprint == key_fingerprint
    )
    messages_query = (
        select(func.count(Message.id))
        .join(ChatSession, Message.session_id == ChatSession.id)
        .where(ChatSession.api_key_fingerprint == key_fingerprint)
    )
    totals = db.execute(
        select(
            func.coalesce(func.sum(ChatSession.total_input_tokens), 0),
            func.coalesce(func.sum(ChatSession.total_output_tokens), 0),
            func.coalesce(func.sum(ChatSession.total_cost), 0.0),
        ).where(ChatSession.api_key_fingerprint == key_fingerprint)
    ).one()
    return UsageOut(
        sessions=db.scalar(sessions_query) or 0,
        messages=db.scalar(messages_query) or 0,
        input_tokens=int(totals[0]),
        output_tokens=int(totals[1]),
        estimated_cost=float(totals[2]),
    )
