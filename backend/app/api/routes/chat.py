import json
import logging
import os
from typing import List

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analysis.ai_summary import build_analysis_context, _get_document_context
from app.api.routes.auth import get_current_user
from app.database import get_db
from app.models.table_class import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


@router.post("/chat")
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI service not configured.")

    context = build_analysis_context(db, current_user.user_id)
    doc_context = _get_document_context(db, current_user.user_id)

    if context:
        data_section = f"--- TRACKING DATA ---\n{json.dumps(context, indent=2, default=str)}"
    else:
        data_section = "No tracking data available yet."

    doc_section = (
        f"\n\n--- HEALTH DOCUMENTS ---\n{doc_context}" if doc_context else ""
    )

    system_prompt = f"""You are a health data assistant helping a user explore their personal food and symptom tracking data. You have access to a statistical summary of their data below.

Answer questions clearly and concisely. Reference specific numbers from the data where relevant. Be honest when the data is insufficient to draw a conclusion. Do not make medical diagnoses or treatment recommendations.

{data_section}{doc_section}"""

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user.")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=system_prompt,
        messages=messages,
    )

    return {"reply": response.content[0].text}
