import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile

from app.db import get_session
from app.extract import EmptyDocument, UnsupportedFormat, process_cv
from app.models import CV
from app.outbox import add_event

router = APIRouter(prefix="/cvs", tags=["cvs"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def current_user_id(x_user_id: str | None = Header(None)) -> uuid.UUID:
    """The gateway validates the JWT and sets X-User-Id; this service trusts it.

    That is safe only because the service port is not published outside Docker.
    """
    try:
        return uuid.UUID(x_user_id)
    except (TypeError, ValueError):
        raise HTTPException(401, "missing or invalid user id")


def _summary(cv: CV) -> dict:
    return {
        "filename": cv.filename,
        "format": cv.file_format,
        "chars": cv.char_count,
        "updated_at": cv.updated_at,
        "preview": cv.text[:300],
    }


@router.put("/me")
async def upload_cv(
    file: UploadFile,
    user_id: uuid.UUID = Depends(current_user_id),
    session=Depends(get_session),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large (max 2 MB)")
    try:
        fmt, text = process_cv(data)
    except UnsupportedFormat as e:
        raise HTTPException(415, str(e))
    except EmptyDocument as e:
        raise HTTPException(422, str(e))

    cv = await session.get(CV, user_id)
    if cv is None:
        cv = CV(user_id=user_id)
        session.add(cv)
    cv.filename = os.path.basename(file.filename or "cv")[:255]
    cv.file_format = fmt
    cv.text = text
    cv.char_count = len(text)
    add_event(session, str(user_id), "cv.updated", {"user_id": str(user_id), "text": text})
    await session.commit()  # CV and outbox row are committed atomically
    await session.refresh(cv)
    return _summary(cv)


@router.get("/me")
async def get_cv(user_id: uuid.UUID = Depends(current_user_id), session=Depends(get_session)):
    cv = await session.get(CV, user_id)
    if cv is None:
        raise HTTPException(404, "no CV uploaded")
    return _summary(cv)


@router.delete("/me", status_code=204)
async def delete_cv(user_id: uuid.UUID = Depends(current_user_id), session=Depends(get_session)):
    cv = await session.get(CV, user_id)
    if cv is None:
        raise HTTPException(404, "no CV uploaded")
    await session.delete(cv)
    add_event(session, str(user_id), "cv.deleted", {"user_id": str(user_id)})
    await session.commit()
