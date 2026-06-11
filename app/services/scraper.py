from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-().]{7,}\d)")

SKIP_EMAIL_SUFFIXES = {
    "example.com", "sentry.io", "wixpress.com", "png", "jpg", "jpeg", "gif", "svg",
    "webp", "js", "css", "woff", "woff2",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _clean_email(email: str) -> str | None:
    email = email.lower().strip().rstrip(".")
    if "@" not in email:
        return None
    domain = email.split("@")[-1]
    if any(domain.endswith(s) for s in SKIP_EMAIL_SUFFIXES):
        return None
    if email.startswith("noreply") or email.startswith("no-reply"):
        return None
    return email


def _base_url(url: str) -> str:
    parsed = urlparse(url if url.startswith("http") else "https://" + url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _extract_text(soup: BeautifulSoup, max_len: int = 400) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    return text[:max_len]


def _guess_company_name(soup: BeautifulSoup, domain: str) -> str:
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        for sep in ["|", "-", "–", "—", ":"]:
            if sep in title:
                part = title.split(sep)[0].strip()
                if len(part) > 2:
                    return part
        if len(title) < 80:
            return title
    return domain.split(".")[0].replace("-", " ").title()


async def _fetch_html(client: httpx.AsyncClient, url: str) -> tuple[str, str | None]:
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code >= 400:
            return url, None
        ctype = resp.headers.get("content-type", "")
        if "text/html" not in ctype and "application/xhtml" not in ctype:
            return url, None
        return url, resp.text
    except Exception:
        return url, None


def _paths_for_mode(fast: bool) -> list[str]:
    if fast:
        return ["", "/contact", "/contact-us"]
    return ["", "/contact", "/contact-us", "/about", "/about-us"]


async def scrape_website(url: str, *, fast: bool = True) -> dict[str, str | list[str]]:
    base = _base_url(url)
    domain = urlparse(base).netloc.lower().lstrip("www.")
    paths = _paths_for_mode(fast)

    emails: set[str] = set()
    phones: set[str] = set()
    descriptions: list[str] = []
    company_name = ""

    timeout = 8 if fast else 12
    async with httpx.AsyncClient(timeout=timeout, headers=HEADERS, follow_redirects=True) as client:
        page_urls = [base if p == "" else urljoin(base, p) for p in paths]
        fetched = await asyncio.gather(*[_fetch_html(client, u) for u in page_urls])

        for page_url, html in fetched:
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            if not company_name:
                company_name = _guess_company_name(soup, domain)

            for email in EMAIL_RE.findall(html):
                cleaned = _clean_email(email)
                if cleaned:
                    emails.add(cleaned)

            for phone in PHONE_RE.findall(html):
                p = " ".join(phone.split())
                if 8 <= len(re.sub(r"\D", "", p)) <= 18:
                    phones.add(p)

            path = urlparse(page_url).path or "/"
            if path in ("", "/") or "about" in path or "company" in path:
                text = _extract_text(soup)
                if len(text) > 60:
                    descriptions.append(text)

    return {
        "company_name": company_name,
        "website": base,
        "domain": domain,
        "emails": sorted(emails)[:5],
        "phone": next(iter(phones), ""),
        "description": descriptions[0] if descriptions else "",
    }
