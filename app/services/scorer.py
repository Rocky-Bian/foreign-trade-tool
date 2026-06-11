from __future__ import annotations

import asyncio
import json

from openai import OpenAI

from app.config import settings
from app.products import ProductProfile


def _rule_score(product: ProductProfile, title: str, snippet: str, description: str) -> tuple[int, str, str]:
    text = f"{title} {snippet} {description}".lower()
    score = 40
    reasons: list[str] = []

    positive = [
        "distributor", "dealer", "wholesaler", "supplier", "trading",
        "laboratory", "lab", "instrument", "equipment", "moisture",
        "weighing", "scale", "analyzer", "sensor", "inline", "process",
        "industrial", "food", "grain", "pharma", "chemical", "testing",
    ]
    negative = [
        "wikipedia", "youtube", "facebook", "linkedin", "job", "career",
        "news", "blog post", "marketplace", "free download", "manual pdf",
    ]

    for kw in positive:
        if kw in text:
            score += 4
            if len(reasons) < 2:
                reasons.append(kw)

    for kw in negative:
        if kw in text:
            score -= 15

    if product.id == "halogen_moisture":
        if any(k in text for k in ["distributor", "dealer", "wholesaler", "trading"]):
            score += 10
        customer_guess = "distributor"
    else:
        if any(k in text for k in ["distributor", "dealer", "wholesaler"]):
            score += 8
            customer_guess = "distributor"
        elif any(k in text for k in ["food", "grain", "plant", "factory", "production", "manufacturer"]):
            score += 8
            customer_guess = "end customer"
        else:
            customer_guess = "unknown"

    score = max(0, min(100, score))
    reason = "Matched keywords: " + ", ".join(reasons) if reasons else "Basic keyword match"
    return score, reason, customer_guess


def _score_with_openai(
    product: ProductProfile,
    *,
    company_name: str,
    website: str,
    country: str,
    description: str,
    title: str,
    snippet: str,
) -> tuple[int, str, str]:
    prompt = f"""Score this B2B lead for foreign trade outreach.

Product: {product.name_en}
ICP: {product.icp_hint}
Country hint: {country or "unknown"}

Company: {company_name}
Website: {website}
Google title: {title}
Google snippet: {snippet}
Website description: {description[:600]}

Return JSON only:
{{
  "score": 0-100,
  "reason": "one sentence in Chinese explaining fit",
  "customer_type_guess": "distributor|dealer|end customer|unknown"
}}

Score high (70+) for clear distributors/dealers or relevant end manufacturers.
Score low (<40) for irrelevant sites, marketplaces, news, job boards."""

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    score = int(data.get("score", 50))
    reason = str(data.get("reason", ""))
    ctype = str(data.get("customer_type_guess", "unknown"))
    return max(0, min(100, score)), reason, ctype


async def score_lead(
    product: ProductProfile,
    *,
    company_name: str,
    website: str,
    country: str,
    description: str,
    title: str,
    snippet: str,
    fast: bool = True,
) -> tuple[int, str, str]:
    if fast or not settings.openai_api_key:
        return _rule_score(product, title, snippet, description)

    try:
        return await asyncio.to_thread(
            _score_with_openai,
            product,
            company_name=company_name,
            website=website,
            country=country,
            description=description,
            title=title,
            snippet=snippet,
        )
    except Exception:
        return _rule_score(product, title, snippet, description)
