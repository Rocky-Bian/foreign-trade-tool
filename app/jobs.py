from __future__ import annotations

import asyncio
import io
import uuid
from datetime import datetime, timezone

from openpyxl import Workbook

from app.config import settings
from app.models import JobProgress, JobResult, JobStatus, Lead, SearchRequest
from app.products import get_product
from app.services.keyword_generator import generate_queries
from app.services.scorer import score_lead
from app.services.scraper import scrape_website
from app.services.search import resolve_search_provider, search_concurrency, search_web, normalize_domain


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobResult] = {}
        self._lock = asyncio.Lock()

    def get(self, job_id: str) -> JobResult | None:
        return self._jobs.get(job_id)

    async def create(self, req: SearchRequest) -> JobResult:
        product = get_product(req.product_id)
        job = JobResult(
            id=str(uuid.uuid4()),
            product_id=product.id,
            product_name=product.name,
            created_at=datetime.now(timezone.utc),
            progress=JobProgress(status=JobStatus.pending, message="等待开始"),
        )
        async with self._lock:
            self._jobs[job.id] = job

        if settings.is_vercel:
            await self._run(job.id, req)
            return self._jobs[job.id]

        asyncio.create_task(self._run(job.id, req))
        return job

    async def _update(self, job_id: str, **kwargs) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            for key, value in kwargs.items():
                setattr(job, key, value)

    async def _update_progress(self, job_id: str, **kwargs) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            for key, value in kwargs.items():
                setattr(job.progress, key, value)

    async def _run(self, job_id: str, req: SearchRequest) -> None:
        product = get_product(req.product_id)

        if settings.is_vercel:
            req.max_queries = min(req.max_queries, 8)
            req.max_results_per_query = min(req.max_results_per_query, 5)

        provider = resolve_search_provider(req.search_provider)
        search_sem = asyncio.Semaphore(search_concurrency(provider))
        process_sem = asyncio.Semaphore(12 if req.fast_mode else 6)

        try:
            await self._update_progress(
                job_id,
                status=JobStatus.running,
                message="正在生成搜索关键词…",
            )

            queries = await generate_queries(
                product,
                req.countries,
                req.customer_types,
                req.max_queries,
            )
            await self._update(job_id, queries=queries)

            await self._update_progress(
                job_id,
                total_queries=len(queries),
                completed_queries=0,
                total_steps=len(queries),
                completed_steps=0,
                message=f"并行搜索 {len(queries)} 条关键词（{provider}）…",
            )

            raw_hits: list[dict] = []
            completed = 0
            lock = asyncio.Lock()

            async def run_query(query: str) -> list[dict]:
                nonlocal completed
                async with search_sem:
                    hits = await search_web(
                        query,
                        num=req.max_results_per_query,
                        provider=provider,
                    )
                async with lock:
                    completed += 1
                    await self._update_progress(
                        job_id,
                        completed_queries=completed,
                        completed_steps=completed,
                        message=f"搜索 {completed}/{len(queries)}",
                    )
                return hits

            batch_results = await asyncio.gather(*[run_query(q) for q in queries])
            for hits in batch_results:
                raw_hits.extend(hits)

            by_domain: dict[str, dict] = {}
            for hit in raw_hits:
                domain = normalize_domain(hit.get("link", ""))
                if not domain:
                    continue
                if domain not in by_domain:
                    by_domain[domain] = hit

            total_steps = len(queries) + len(by_domain)
            await self._update_progress(
                job_id,
                message=f"共 {len(by_domain)} 个网站，并行抓取分析…",
                leads_found=len(by_domain),
                total_steps=total_steps,
                completed_steps=len(queries),
            )

            country_hint = ", ".join(req.countries) if req.countries else product.market_label
            scored = 0
            score_lock = asyncio.Lock()

            async def process_hit(domain: str, hit: dict) -> Lead:
                nonlocal scored
                async with process_sem:
                    if hit.get("source") == "demo":
                        scraped = {
                            "company_name": hit.get("title", domain),
                            "website": hit.get("link", ""),
                            "emails": [f"info@{domain}"],
                            "phone": "",
                            "description": hit.get("snippet", ""),
                        }
                    else:
                        scraped = await scrape_website(hit["link"], fast=req.fast_mode)

                    score, reason, ctype = await score_lead(
                        product,
                        company_name=str(scraped.get("company_name") or hit.get("title", domain)),
                        website=str(scraped.get("website") or hit.get("link", "")),
                        country=country_hint,
                        description=str(scraped.get("description") or hit.get("snippet", "")),
                        title=hit.get("title", ""),
                        snippet=hit.get("snippet", ""),
                        fast=req.fast_mode,
                    )

                async with score_lock:
                    scored += 1
                    await self._update_progress(
                        job_id,
                        leads_scored=scored,
                        completed_steps=len(queries) + scored,
                        message=f"分析 {scored}/{len(by_domain)}",
                    )

                return Lead(
                    company_name=str(scraped.get("company_name") or hit.get("title", domain)),
                    website=str(scraped.get("website") or hit.get("link", "")),
                    country=country_hint,
                    emails=list(scraped.get("emails") or []),
                    phone=str(scraped.get("phone") or ""),
                    description=str(scraped.get("description") or hit.get("snippet", "")),
                    score=score,
                    reason=reason,
                    customer_type_guess=ctype,
                    source_query=hit.get("query", ""),
                )

            leads = await asyncio.gather(
                *[process_hit(domain, hit) for domain, hit in by_domain.items()]
            )
            leads = sorted(leads, key=lambda x: x.score, reverse=True)

            await self._update(job_id, leads=leads)
            await self._update_progress(
                job_id,
                status=JobStatus.completed,
                completed_steps=total_steps,
                message=f"完成，共 {len(leads)} 条线索",
            )
        except Exception as exc:
            await self._update(job_id, error=str(exc))
            await self._update_progress(
                job_id,
                status=JobStatus.failed,
                message="任务失败",
            )


job_store = JobStore()


def export_leads_xlsx(job: JobResult) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    headers = [
        "评分", "公司名", "网站", "国家/市场", "邮箱", "电话",
        "客户类型", "简介", "匹配理由", "来源搜索词",
    ]
    ws.append(headers)

    for lead in job.leads:
        ws.append([
            lead.score,
            lead.company_name,
            lead.website,
            lead.country,
            "; ".join(lead.emails),
            lead.phone,
            lead.customer_type_guess,
            lead.description[:500],
            lead.reason,
            lead.source_query,
        ])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_leads_csv(job: JobResult) -> str:
    import csv
    import io as io_mod

    buf = io_mod.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "score", "company_name", "website", "country", "emails", "phone",
        "customer_type", "description", "reason", "source_query",
    ])
    for lead in job.leads:
        writer.writerow([
            lead.score,
            lead.company_name,
            lead.website,
            lead.country,
            "; ".join(lead.emails),
            lead.phone,
            lead.customer_type_guess,
            lead.description,
            lead.reason,
            lead.source_query,
        ])
    return buf.getvalue()
