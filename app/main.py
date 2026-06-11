from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.jobs import export_leads_csv, export_leads_xlsx, job_store
from app.models import (
    GoogleSettingsRequest,
    GoogleSettingsResponse,
    JobResult,
    ProductInfo,
    ProductsResponse,
    SearchRequest,
)
from app.products import PRODUCTS, market_options
from app.services.search import PROVIDER_LABELS, active_search_provider
from app.settings_store import google_configured, save_google_keys

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="外贸客户发现工具", version="0.1.0")


@app.get("/api/config")
def get_config() -> dict[str, str | bool]:
    provider = active_search_provider("auto")
    return {
        "search_provider": provider,
        "search_provider_label": PROVIDER_LABELS.get(provider, provider),
        "is_vercel": settings.is_vercel,
        "serpapi_configured": bool(settings.serpapi_key),
        "google_cse_configured": google_configured(),
        "google_api_key_hint": _mask_key(settings.google_api_key),
        "google_cse_id": settings.google_cse_id,
        "openai_configured": bool(settings.openai_api_key),
    }


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


@app.get("/api/settings/google", response_model=GoogleSettingsResponse)
def get_google_settings() -> GoogleSettingsResponse:
    return GoogleSettingsResponse(
        google_api_key=settings.google_api_key,
        google_cse_id=settings.google_cse_id,
        configured=google_configured(),
    )


@app.post("/api/settings/google", response_model=GoogleSettingsResponse)
def update_google_settings(body: GoogleSettingsRequest) -> GoogleSettingsResponse:
    if not body.google_api_key.strip() or not body.google_cse_id.strip():
        raise HTTPException(status_code=400, detail="请填写 API Key 和搜索引擎 ID")
    if settings.is_vercel:
        raise HTTPException(
            status_code=400,
            detail="Vercel 上请在 Project Settings → Environment Variables 配置 GOOGLE_API_KEY 和 GOOGLE_CSE_ID",
        )
    save_google_keys(body.google_api_key, body.google_cse_id)
    return GoogleSettingsResponse(
        google_api_key=body.google_api_key.strip(),
        google_cse_id=body.google_cse_id.strip(),
        configured=True,
    )


@app.get("/api/products", response_model=ProductsResponse)
def list_products() -> ProductsResponse:
    items: list[ProductInfo] = []
    for p in PRODUCTS.values():
        markets = [{"code": c, "name": n} for c, n in market_options(p.id)]
        items.append(
            ProductInfo(
                id=p.id,
                name=p.name,
                name_en=p.name_en,
                description=p.description,
                customer_types=p.customer_types,
                market_label=p.market_label,
                markets=markets,
            )
        )
    return ProductsResponse(products=items)


@app.post("/api/search", response_model=JobResult)
async def start_search(req: SearchRequest) -> JobResult:
    if req.product_id not in PRODUCTS:
        raise HTTPException(status_code=400, detail="Unknown product")
    return await job_store.create(req)


@app.get("/api/search/{job_id}", response_model=JobResult)
def get_search(job_id: str) -> JobResult:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/search/{job_id}/export")
def export_search(job_id: str, format: str = "xlsx") -> Response:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.progress.status != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    filename_base = f"leads_{job.product_id}_{job.id[:8]}"
    if format == "csv":
        content = export_leads_csv(job)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.csv"'},
        )

    content = export_leads_xlsx(job)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}.xlsx"'},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
