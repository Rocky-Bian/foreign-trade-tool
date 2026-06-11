from __future__ import annotations

import json
import itertools

from openai import OpenAI

from app.config import settings
from app.products import ProductProfile, market_options


def _country_name(code: str, product_id: str) -> str:
    for c, name in market_options(product_id):
        if c == code:
            return name
    return code


def build_queries_template(
    product: ProductProfile,
    countries: list[str],
    customer_types: list[str],
    max_queries: int,
) -> list[str]:
    types = customer_types or product.customer_types[:3]
    country_codes = countries or product.markets[:5]

    queries: list[str] = []
    seen: set[str] = set()

    for template, country_code, ctype in itertools.product(
        product.keyword_templates, country_codes, types
    ):
        country = _country_name(country_code, product.id)
        q = template.format(customer_type=ctype, country=country).strip()
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(q)
        if len(queries) >= max_queries:
            break

    return queries


async def generate_queries(
    product: ProductProfile,
    countries: list[str],
    customer_types: list[str],
    max_queries: int,
) -> list[str]:
    base = build_queries_template(product, countries, customer_types, max_queries)

    if not settings.openai_api_key:
        return base

    country_names = [_country_name(c, product.id) for c in (countries or product.markets[:5])]
    types = customer_types or product.customer_types

    prompt = f"""You help B2B foreign trade lead generation.

Product: {product.name_en} ({product.name})
Description: {product.description}
Target customer types: {", ".join(types)}
Target countries: {", ".join(country_names)}
ICP: {product.icp_hint}

Generate {max(6, max_queries - len(base))} additional Google search queries in English
to find potential B2B customers (distributors, dealers, or end manufacturers).
Each query should be specific, include country when useful, and avoid duplicates.

Return JSON only: {{"queries": ["query1", "query2", ...]}}"""

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        extra = data.get("queries", [])
        merged: list[str] = []
        seen = set()
        for q in base + extra:
            key = q.lower().strip()
            if key and key not in seen:
                seen.add(key)
                merged.append(q.strip())
            if len(merged) >= max_queries:
                break
        return merged
    except Exception:
        return base
