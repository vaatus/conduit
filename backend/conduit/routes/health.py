# SPDX-License-Identifier: MIT
from fastapi import APIRouter

from ..config import settings

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "lt_inspect_url": settings.LT_INSPECT_URL,
        "lt_gemini_base_url": settings.LT_GEMINI_BASE_URL,
        "lt_mock_mode": settings.LT_MOCK_MODE,
        "gemini_classify_model": settings.GEMINI_MODEL_CLASSIFY,
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
    }
