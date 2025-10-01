import logging
import os

from app.core.db_helper import db_helper
from app.core.models import Study, User
from app.services.demo_service import DemoService
from app.services.study_service import StudyService
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["Демо"])

# Настройка шаблонов
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "app", "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/", response_class=HTMLResponse)
async def demo_main_page(request: Request):
    """Главная страница демо-режима"""
    demo_tokens = DemoService.get_demo_tokens()
    demo_token = demo_tokens.get("access_token") if demo_tokens else ""

    return templates.TemplateResponse(
        "demo_main.html", {"request": request, "demo_token": demo_token}
    )


@router.get("/token")
async def get_demo_token():
    """API endpoint для получения демо-токена"""
    if not DemoService.is_ready():
        raise HTTPException(status_code=500, detail="Демо-режим не готов")

    tokens = DemoService.get_demo_tokens()
    if not tokens or "access_token" not in tokens:
        raise HTTPException(status_code=500, detail="Демо-токен не доступен")

    return JSONResponse(
        {"access_token": tokens["access_token"], "token_type": "bearer"}
    )


@router.get("/results", response_class=HTMLResponse)
async def demo_results_page(
    request: Request, session: AsyncSession = Depends(db_helper.session_getter)
):
    """Страница со списком всех исследований - использует API для данных"""
    # Получаем демо-токен для JavaScript
    demo_tokens = DemoService.get_demo_tokens()
    demo_token = demo_tokens.get("access_token") if demo_tokens else ""

    return templates.TemplateResponse(
        "demo_results.html", {"request": request, "demo_token": demo_token}
    )


@router.get("/studies/{study_id}", response_class=HTMLResponse)
async def demo_study_detail(request: Request, study_id: int):
    """Детальная страница исследования - данные будут загружены через API"""
    demo_tokens = DemoService.get_demo_tokens()
    demo_token = demo_tokens.get("access_token") if demo_tokens else ""

    return templates.TemplateResponse(
        "demo_study_detail.html",
        {"request": request, "study_id": study_id, "demo_token": demo_token},
    )
