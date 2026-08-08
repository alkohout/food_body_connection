import json
import logging
import os
from typing import List

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analysis import data_tools
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
    # JS Date.getTimezoneOffset(); needed so time-of-day claims are in the
    # user's zone rather than UTC.
    tz_offset: int = 0


# Model choice: tool selection over an ambiguous question is the hard part here
# — picking the right tool and arguments from a vague "show me my headaches in
# March" is what determines whether the answer is right. Haiku (used by the
# summary endpoint) is weaker at that. Adjust if the cost is not worth it.
_CHAT_MODEL = "claude-opus-5"

# Thinking is left at its default (on). Disabling it on this model can make the
# model write a tool call into its visible text instead of emitting a tool_use
# block — the turn succeeds, the call never runs, and nothing errors. That is
# precisely the failure mode a tool-driven feature cannot afford.
_CHAT_EFFORT = "medium"      # interactive chat; raise for harder analysis
_CHAT_MAX_TOKENS = 8000      # covers thinking + reply; nginx caps the turn at 120s
_MAX_TOOL_ROUNDS = 4         # bounds latency and stops runaway loops


def _run_tool_loop(client, system_prompt, messages, db, user_id, tz_offset):
    """Drive the request/tool/response cycle until the model stops calling tools.

    Written as an explicit loop rather than using the SDK's tool runner: the
    frontend renders the rows the model looked at, so the loop needs to capture
    tool output as it goes, and the runner is still beta.

    Returns (final_response, table_for_display, summed_usage).
    """
    convo = list(messages)
    table = None
    usage = {"input_tokens": 0, "output_tokens": 0}

    for _ in range(_MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=_CHAT_MODEL,
            max_tokens=_CHAT_MAX_TOKENS,
            output_config={"effort": _CHAT_EFFORT},
            system=system_prompt,
            tools=data_tools.TOOLS,
            messages=convo,
        )
        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            return response, table, usage

        # Echo the assistant turn back verbatim — dropping the tool_use blocks
        # would orphan the tool_result ids that follow.
        convo.append({"role": "assistant", "content": response.content})

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            output = data_tools.run_tool(
                block.name, block.input, db, user_id, tz_offset
            )
            # Keep the last real table for the UI; a bare error has nothing to show.
            if isinstance(output, dict) and output.get("rows"):
                table = {"title": _describe_call(block.name, block.input), **output}
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(output, default=str),
                "is_error": bool(isinstance(output, dict) and output.get("error")),
            })

        # All results for one assistant turn go back in a single user message.
        convo.append({"role": "user", "content": results})

    # Ran out of rounds. Ask for a final answer with tools withheld so the model
    # has to respond in prose instead of looping again.
    response = client.messages.create(
        model=_CHAT_MODEL,
        max_tokens=_CHAT_MAX_TOKENS,
        output_config={"effort": _CHAT_EFFORT},
        system=system_prompt
        + "\n\nYou have used your tool budget for this question. "
          "Answer now with what you have, and say what you could not check.",
        messages=convo,
    )
    usage["input_tokens"] += response.usage.input_tokens
    usage["output_tokens"] += response.usage.output_tokens
    return response, table, usage


def _describe_call(name, args):
    """Short human-readable caption for the table shown to the user."""
    args = args or {}
    names = ", ".join(args.get("names") or []) or "all items"
    span = ""
    if args.get("date_from") or args.get("date_to"):
        span = f" ({args.get('date_from', 'start')} to {args.get('date_to', 'now')})"
    if name == "query_logs":
        return f"{args.get('kind', 'entries')} entries: {names}{span}"
    if name == "aggregate_logs":
        return f"{args.get('kind', 'entries')} by {args.get('group_by')}: {names}{span}"
    if name == "get_checkins":
        return f"Daily check-ins{span}"
    return "Tracked items"


@router.post("/chat")
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI service not configured.")

    context = build_analysis_context(db, current_user.user_id, body.tz_offset)
    doc_context = _get_document_context(db, current_user.user_id)

    if context:
        data_section = f"--- TRACKING DATA ---\n{json.dumps(context, indent=2, default=str)}"
    else:
        data_section = "No tracking data available yet."

    doc_section = (
        f"\n\n--- HEALTH DOCUMENTS ---\n{doc_context}" if doc_context else ""
    )

    system_prompt = f"""You are a health data assistant helping a user explore their personal food and symptom tracking data. You have access to a statistical summary of their data below, and to tools that read the underlying records directly.

Answer questions clearly and concisely. Reference specific numbers from the data where relevant. Be honest when the data is insufficient to draw a conclusion. Do not make medical diagnoses or treatment recommendations.

The summary below is aggregated. When the user asks to see specific entries, or asks a question the summary cannot answer (a particular date range, a specific food or symptom, counts grouped a particular way), use the tools to look up the actual records rather than guessing or saying you lack the data.

Names must match what the user actually logs. If you are unsure of the exact name of a food, symptom or medication, call list_tracked_items first — matching is case-insensitive but otherwise exact, so a guessed name returns nothing.

The rows a tool returns are displayed to the user as a table beneath your reply, so do not repeat every row back in prose. Summarise what the rows show and point out what is notable.

Keep responses focused and brief — lead with the answer, then a few specific observations. Do not pad with caveats or restate the question.

Do not narrate corrections to yourself mid-answer. If you notice you have miscounted while writing, state the correct figure and continue; do not write out the mistake and the fix.

{data_section}{doc_section}"""

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user.")

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response, table, usage = _run_tool_loop(
            client, system_prompt, messages, db, current_user.user_id, body.tz_offset
        )
    except anthropic.BadRequestError as e:
        logger.error("Anthropic bad request: %s", e)
        raise HTTPException(status_code=400, detail="The request was too large or malformed. Try removing some documents or shortening your message.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="AI service rate limit reached. Please wait a moment and try again.")
    except anthropic.APIStatusError as e:
        logger.error("Anthropic API error %s: %s", e.status_code, e.message)
        raise HTTPException(status_code=502, detail="AI service returned an error. Please try again.")
    except anthropic.APIConnectionError as e:
        logger.error("Anthropic connection error: %s", e)
        raise HTTPException(status_code=502, detail="Could not reach AI service. Please try again.")

    reply = "\n\n".join(
        b.text for b in response.content if b.type == "text" and b.text.strip()
    )

    return {
        "reply": reply or "I couldn't produce an answer for that — try rephrasing.",
        "table": table,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
    }
