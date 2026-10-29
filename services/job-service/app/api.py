from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_dict(j: Job) -> dict:
    return {
        "id": str(j.id),
        "title": j.title,
        "company": j.company,
        "location": j.location,
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "salary_currency": j.salary_currency,
        "skills": j.skills,
        "status": j.status,
        "first_seen_at": j.first_seen_at,
        "sources": [{"source": s.source, "url": s.url} for s in j.sources],
    }


@router.get("")
async def search_jobs(
    q: str | None = Query(None, description="Full-text search keywords"),
    skills: list[str] = Query(default=[], description="Job must have ALL of these skills"),
    location: str | None = None,
    min_salary: int | None = Query(None, description="Job maximum salary must be >= this value"),
    currency: str | None = Query(None, description="VND or USD"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session=Depends(get_session),
):
    conds = [Job.status == "active"]
    rank = None

    if q:
        tsq = func.websearch_to_tsquery(literal_column("'simple'::regconfig"), q)
        conds.append(Job.search_vector.op("@@")(tsq))
        rank = func.ts_rank(Job.search_vector, tsq)
    if skills:
        conds.append(Job.skills.contains([s.lower() for s in skills]))
    if location:
        conds.append(Job.location.ilike(f"%{location}%"))
    if min_salary is not None:
        conds.append(func.coalesce(Job.salary_max, Job.salary_min) >= min_salary)
    if currency:
        conds.append(Job.salary_currency == currency.upper())

    total = await session.scalar(select(func.count()).select_from(Job).where(*conds))

    order = rank.desc() if rank is not None else Job.first_seen_at.desc()
    stmt = (
        select(Job)
        .options(selectinload(Job.sources))
        .where(*conds)
        .order_by(order, Job.id)
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.scalars(stmt)).all()
    return {"total": total, "limit": limit, "offset": offset, "items": [_to_dict(j) for j in rows]}


@router.get("/{job_id}")
async def get_job(job_id: str, session=Depends(get_session)):
    try:
        job = await session.scalar(
            select(Job).options(selectinload(Job.sources)).where(Job.id == job_id)
        )
    except Exception:
        raise HTTPException(status_code=422, detail="invalid job id")
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {**_to_dict(job), "description": job.description}
