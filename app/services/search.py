from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

import httpx
from ddgs import DDGS

from app.config import settings


SKIP_DOMAINS = {
    "google.com", "google.co.th", "google.com.vn", "google.co.id",
    "youtube.com", "facebook.com", "linkedin.com", "instagram.com",
    "twitter.com", "x.com", "wikipedia.org", "amazon.com", "alibaba.com",
    "aliexpress.com", "made-in-china.com", "globalsources.com",
    "indiamart.com", "ebay.com", "reddit.com", "quora.com",
    "yellowpages.com", "yelp.com", "indeed.com", "glassdoor.com",
}

PROVIDER_LABELS = {
    "serpapi": "SerpAPI（Google 搜索）",
    "google_cse": "Google 免费搜索（100次/天）",
    "duckduckgo": "DuckDuckGo（免费）",
    "demo": "演示模式",
}


def normalize_domain(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    domain = (parsed.netloc or parsed.path).lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def is_skippable_url(url: str) -> bool:
    domain = normalize_domain(url)
    if not domain:
        return True
    for skip in SKIP_DOMAINS:
        if domain == skip or domain.endswith("." + skip):
            return True
    return False


def _filter_hits(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for hit in hits:
        link = hit.get("link", "")
        if is_skippable_url(link):
            continue
        out.append(hit)
    return out


def resolve_search_provider(preference: str = "auto") -> str:
    if preference == "duckduckgo":
        return "duckduckgo"
    if preference == "google_cse":
        if settings.google_api_key and settings.google_cse_id:
            return "google_cse"
        return "duckduckgo"
    if preference == "serpapi" and settings.serpapi_key:
        return "serpapi"

    if settings.serpapi_key:
        return "serpapi"
    return "duckduckgo"


def active_search_provider(preference: str = "auto") -> str:
    return resolve_search_provider(preference)


def search_concurrency(provider: str) -> int:
    if provider == "google_cse":
        return 8
    if provider == "serpapi":
        return 6
    return 4


async def search_web(query: str, num: int = 10, *, provider: str | None = None) -> list[dict[str, str]]:
    chosen = provider or resolve_search_provider()

    if chosen == "serpapi":
        hits = await _search_serpapi(query, num)
    elif chosen == "google_cse":
        hits = await _search_google_cse(query, num)
    else:
        hits = await _search_duckduckgo(query, num)

    if hits:
        return _filter_hits(hits)

    return _demo_results(query, num)


search_google = search_web


async def _search_serpapi(query: str, num: int) -> list[dict[str, str]]:
    params = {
        "engine": "google",
        "q": query,
        "api_key": settings.serpapi_key,
        "num": min(num, 20),
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "query": query,
            "source": "serpapi",
        }
        for item in data.get("organic_results", [])
        if item.get("link")
    ]


async def _search_google_cse(query: str, num: int) -> list[dict[str, str]]:
    params = {
        "key": settings.google_api_key,
        "cx": settings.google_cse_id,
        "q": query,
        "num": min(num, 10),
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "query": query,
            "source": "google_cse",
        }
        for item in data.get("items", [])
        if item.get("link")
    ]


def _search_duckduckgo_sync(query: str, num: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=min(num, 25)):
            link = item.get("href", "")
            if not link:
                continue
            results.append(
                {
                    "title": item.get("title", ""),
                    "link": link,
                    "snippet": item.get("body", ""),
                    "query": query,
                    "source": "duckduckgo",
                }
            )
    return results


async def _search_duckduckgo(query: str, num: int) -> list[dict[str, str]]:
    try:
        return await asyncio.to_thread(_search_duckduckgo_sync, query, num)
    except Exception:
        return []


def _demo_results(query: str, num: int) -> list[dict[str, str]]:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower())[:40].strip("-")
    samples = [
        {
            "title": f"Demo Lab Equipment Distributor — {query[:30]}",
            "link": f"https://example-{slug}-1.com",
            "snippet": "Laboratory instruments, moisture analyzers, weighing equipment distributor.",
            "query": query,
            "source": "demo",
        },
        {
            "title": "Demo Industrial Instruments Dealer",
            "link": f"https://example-{slug}-2.com",
            "snippet": "Process measurement, inline sensors, industrial automation solutions.",
            "query": query,
            "source": "demo",
        },
    ]
    return samples[: min(num, 2)]
