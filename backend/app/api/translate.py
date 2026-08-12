"""翻译端点（通用工具，国内/国外舆情详情弹窗共用）。

路径：`POST /api/translate`（依赖 api_router 的 /api 前缀，需登录）。
入参：{ text, target_lang='zh', source_lang='auto' }
出参：{ translated_text }
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.translation_service import TranslationError, translate_text

translate_router = APIRouter(
    tags=["translate"],
    dependencies=[Depends(get_current_user)],
)


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    target_lang: str = "zh"
    source_lang: str = "auto"


class TranslateResponse(BaseModel):
    translated_text: str


@translate_router.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest) -> TranslateResponse:
    try:
        result = translate_text(req.text, req.target_lang, req.source_lang)
    except TranslationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TranslateResponse(translated_text=result)
