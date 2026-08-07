"""Executable competition benchmark dashboard endpoint."""

from fastapi import APIRouter, Query

from app.services.benchmark_service import get_benchmark_summary

router = APIRouter(prefix="/api/v1/benchmarks", tags=["benchmarks"])


@router.get("/summary")
async def benchmark_summary(refresh: bool = Query(default=False)):
    return await get_benchmark_summary(force_refresh=refresh)
