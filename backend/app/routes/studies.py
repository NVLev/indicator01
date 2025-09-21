from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pathlib import Path
import json
import logging

from ..services.security import get_current_user

router = APIRouter(prefix="/studies", tags=["studies"])


@router.post("/upload-study")
async def upload_study(
    file: UploadFile,
    current_user = Depends(get_current_user)
):
    pass
    # Validate ZIP file
    # Extract DICOM metadata
    # Queue for processing
    # Return study ID and status