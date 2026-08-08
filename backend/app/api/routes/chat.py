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
from app.models.table_class import Allergen, Symptom, User

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


# Two models, split by which half carries the tokens.
#
# Deciding WHICH tool to call, with which arguments, is the half that can
# quietly produce a wrong answer — and its input is just the tool schemas plus
# the question (~1.5k tokens) however much data comes back. So the expensive
# model sits on the small half, and never sees the health documents at all.
#
# Writing the answer carries everything: the statistical summary (2.3k), the
# documents (4.9k) and every row the tools returned. That is the big half, and
# it is the easy half — turning rows already in front of you into prose. Haiku
# does it at a fifth of the price.
#
# Measured before the split: 8.7k tokens resent per tool round, 26k for a
# 3-round question, $0.13 per question with Opus carrying all of it.
_TOOL_MODEL = "claude-opus-5"
_TOOL_PRICE = (5.00, 25.00)      # USD per million tokens (input, output)
_TOOL_EFFORT = "low"             # picking a tool is not hard; raise if it misfires

_WRITEUP_MODEL = "claude-haiku-4-5"
_WRITEUP_PRICE = (1.00, 5.00)

# Thinking is left at its default (on) on the tool model. Disabling it can make
# the model write a tool call into its visible text instead of emitting a
# tool_use block — the turn succeeds, the call never runs, and nothing errors.
# That is precisely the failure mode a tool-driven feature cannot afford.
_TOOL_MAX_TOKENS = 4000
_WRITEUP_MAX_TOKENS = 1200
_MAX_TOOL_ROUNDS = 4             # bounds latency and stops runaway loops


def _tracked_names(db, user_id):
    """Compact list of what the user logs, so tool-selection needn't spend a
    round discovering names. ~100 tokens, versus a whole extra round-trip."""
    allergens = sorted(
        (a.allergen_name or "").strip()
        for a in db.query(Allergen).filter(Allergen.user_id == user_id).all()
        if a.allergen_name
    )
    symptoms = sorted(
        (s.symptom_name or "").strip()
        for s in db.query(Symptom).filter(Symptom.user_id == user_id).all()
        if s.symptom_name
    )
    return (
        f"Allergens/foods logged: {', '.join(allergens) or 'none'}\n"
        f"Symptoms logged: {', '.join(symptoms) or 'none'}"
    )


_TOOL_SYSTEM = """You look up entries in a user's health tracking database by calling tools.

Your only job this turn is to fetch the right data. Do not write an explanation \
or an analysis — another step does that. Call the tools you need, then stop.

Match names exactly against the list below (matching is case-insensitive but \
otherwise exact). If the question does not need any lookup, call no tools.

{names}"""


def _run_tool_loop(client, db, user_id, tz_offset, messages):
    """Fetch phase: let the strong model choose tools until it stops calling them.

    Written as an explicit loop rather than using the SDK's tool runner, because
    the frontend renders the rows the model read, so the loop has to capture
    tool output as it goes — and the runner is still beta.

    Returns (collected_results, table_for_display, usage).
    """
    system = [{
        "type": "text",
        "text": _TOOL_SYSTEM.format(names=_tracked_names(db, user_id)),
        # Stable across rounds and across turns, so it caches. Tools render
        # before system, so this breakpoint covers both.
        "cache_control": {"type": "ephemeral"},
    }]

    convo = list(messages)
    collected, table = [], None
    usage = _new_usage()

    for _ in range(_MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=_TOOL_MODEL,
            max_tokens=_TOOL_MAX_TOKENS,
            output_config={"effort": _TOOL_EFFORT},
            system=system,
            tools=data_tools.TOOLS,
            messages=convo,
        )
        _add_usage(usage, response.usage)

        if response.stop_reason != "tool_use":
            break

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
            label = _describe_call(block.name, block.input)
            collected.append({"query": label, "result": output})
            # Keep the last real table for the UI; a bare error has nothing to show.
            if isinstance(output, dict) and output.get("rows"):
                table = {"title": label, **output}
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(output, default=str),
                "is_error": bool(isinstance(output, dict) and output.get("error")),
            })

        # All results for one assistant turn go back in a single user message.
        convo.append({"role": "user", "content": results})

    return collected, table, usage


def _write_up(client, system_blocks, messages, collected):
    """Answer phase: cheap model turns the fetched rows into prose.

    It receives the full context — summary, documents, and every row the tools
    returned — because that is what writing a good answer needs. This is the
    big-input half, which is why it is not on the expensive model.
    """
    convo = list(messages)
    if collected:
        convo.append({
            "role": "user",
            "content": (
                "Here are the results of looking up their data. Answer the question "
                "using these, and do not mention that a lookup step happened:\n\n"
                + json.dumps(collected, indent=2, default=str)
            ),
        })

    response = client.messages.create(
        model=_WRITEUP_MODEL,
        max_tokens=_WRITEUP_MAX_TOKENS,
        system=system_blocks,
        messages=convo,
    )
    return response


def _add_usage(usage, u):
    """Accumulate one response's usage.

    input_tokens is only the UNCACHED remainder — the cached part is reported
    separately, so summing input_tokens alone silently undercounts a cached
    prompt by everything that hit the cache.
    """
    usage["input_tokens"] += u.input_tokens
    usage["cache_write_tokens"] += getattr(u, "cache_creation_input_tokens", 0) or 0
    usage["cache_read_tokens"] += getattr(u, "cache_read_input_tokens", 0) or 0
    usage["output_tokens"] += u.output_tokens
    return usage


def _new_usage():
    return {"input_tokens": 0, "cache_write_tokens": 0,
            "cache_read_tokens": 0, "output_tokens": 0}


def _usd(usage, price):
    """Cache writes cost 1.25x input, cache reads 0.1x."""
    inp, out = price
    return (
        usage["input_tokens"] / 1e6 * inp
        + usage["cache_write_tokens"] / 1e6 * inp * 1.25
        + usage["cache_read_tokens"] / 1e6 * inp * 0.10
        + usage["output_tokens"] / 1e6 * out
    )


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

    writeup_system = [{
        "type": "text",
        "text": f"""You are a health data assistant helping a user explore their personal food and symptom tracking data.

Answer clearly and concisely. Lead with the answer, then a few specific observations. Reference specific numbers where relevant. Be honest when the data is insufficient to draw a conclusion. Do not make medical diagnoses or treatment recommendations, and do not pad with caveats or restate the question.

If lookup results are supplied, they are also displayed to the user as a table beneath your reply — so summarise what they show and point out what is notable rather than repeating every row.

{data_section}{doc_section}""",
        # The summary and documents are identical across every turn of a
        # conversation, and they are the bulk of this prompt — cache them.
        "cache_control": {"type": "ephemeral"},
    }]

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user.")

    client = anthropic.Anthropic(api_key=api_key)
    try:
        collected, table, tool_usage = _run_tool_loop(
            client, db, current_user.user_id, body.tz_offset, messages
        )
        response = _write_up(client, writeup_system, messages, collected)
        write_usage = _add_usage(_new_usage(), response.usage)
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

    # Two models at different prices, so the server computes the cost — the
    # client cannot derive it from token counts alone any more.
    cost = _usd(tool_usage, _TOOL_PRICE) + _usd(write_usage, _WRITEUP_PRICE)

    return {
        "reply": reply or "I couldn't produce an answer for that — try rephrasing.",
        "table": table,
        "cost_usd": round(cost, 6),
        "input_tokens": sum(
            u[k] for u in (tool_usage, write_usage)
            for k in ("input_tokens", "cache_write_tokens", "cache_read_tokens")
        ),
        "output_tokens": tool_usage["output_tokens"] + write_usage["output_tokens"],
        "lookup_tokens": tool_usage,
        "writeup_tokens": write_usage,
    }
