"""Evidence-grounded AI Investigation Copilot endpoint."""
from __future__ import annotations

import io
import re
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from fastapi.responses import StreamingResponse

from config import settings
from services.llm_provider import build_llm_provider
from services.copilot_service import build_grounded_answer

router = APIRouter(tags=["AI Investigation Copilot"])


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    invoice_id: str | None = Field(default=None, max_length=64)
    context_entity_id: str | None = Field(default=None, max_length=64)
    context_entity_type: Literal["invoice", "company", "lender", "gstin"] | None = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=12)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value

    @field_validator("invoice_id")
    @classmethod
    def validate_invoice_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or len(value) > 64 or not value.replace("-", "").replace("/", "").replace(" ", "").isalnum():
            raise ValueError("invoice_id contains unsupported characters")
        return value

    @field_validator("context_entity_id")
    @classmethod
    def validate_context_entity_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or len(value) > 64 or not value.replace("-", "").replace("/", "").replace(" ", "").isalnum():
            raise ValueError("context_entity_id contains unsupported characters")
        return value


@router.post("/copilot/chat")
async def copilot_chat(request: CopilotChatRequest):
    """Plan allowlisted tools, collect verified data, and return a grounded answer."""
    patterns = {
        "invoice": r"INV[-/ ]?\d{4}[-/ ]?\d{3,8}",
        "company": r"CMP\d{3,8}",
        "lender": r"LND\d{3,6}",
        "gstin": r"\d{2}[A-Z0-9]{13}",
    }
    if request.context_entity_id and request.context_entity_type:
        if not re.fullmatch(patterns[request.context_entity_type], request.context_entity_id, re.IGNORECASE):
            raise HTTPException(status_code=422, detail="Context identifier does not match its entity type")
        if request.invoice_id and request.context_entity_type != "invoice":
            raise HTTPException(status_code=422, detail="invoice_id cannot be combined with non-invoice context")
    try:
        return await run_in_threadpool(
            build_grounded_answer,
            request.message,
            [turn.model_dump() for turn in request.history],
            request.invoice_id,
            request.context_entity_id,
            request.context_entity_type,
        )
    except Exception as exc:  # keep unexpected tool/provider details out of the response
        raise HTTPException(status_code=500, detail="Copilot could not complete this investigation.") from exc


@router.get("/copilot/status")
async def copilot_status():
    provider = build_llm_provider(settings)
    return {
        "configured": provider.configured,
        "provider": provider.provider_names[0] if provider.provider_names else "none",
        "fallback_providers": provider.provider_names[1:],
        "mode": "AI" if provider.configured else "Evidence Mode",
    }


@router.get("/copilot/report")
async def copilot_report(invoice_id: str):
    if len(invoice_id) > 64 or not invoice_id.replace("-", "").replace("/", "").replace(" ", "").isalnum():
        raise HTTPException(status_code=422, detail="Invalid invoice identifier")
    result = await run_in_threadpool(
        build_grounded_answer,
        "Generate an investigation summary",
        [],
        invoice_id,
        invoice_id,
        "invoice",
    )
    report_text = result.get("report_text")
    if not report_text or result.get("fallback_reason") == "invoice_not_found":
        raise HTTPException(status_code=404, detail="No verified investigation report data was found")
    canonical_id = result.get("invoice_id") or invoice_id
    filename = f"{canonical_id}-investigation-report.txt"
    return StreamingResponse(
        io.BytesIO(report_text.encode("utf-8")),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
