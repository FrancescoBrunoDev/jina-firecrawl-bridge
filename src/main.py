"""Jina → Firecrawl Bridge — FastAPI application.

Exposes a Firecrawl-compatible REST API backed by Jina AI Reader.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.jina_client import check_health, extract_url
from src.models import (
    CrawlRequest,
    CrawlResponse,
    CrawlStatusResponse,
    HealthResponse,
    ScrapeData,
    ScrapeMetadata,
    ScrapeRequest,
    ScrapeResponse,
)

# ── Logging ────────────────────────────────────────────────────────────

log_level = (os.getenv("LOG_LEVEL") or "info").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jina-firecrawl-bridge")


# ── Auth check ─────────────────────────────────────────────────────────


def _check_auth(request: Request) -> None:
    """Verify API key if BRIDGE_API_KEY is configured."""
    api_key = os.getenv("BRIDGE_API_KEY", "").strip()
    if not api_key:
        return  # auth is disabled

    auth_header = request.headers.get("Authorization", "")
    # Accept: Bearer <key> or just <key>
    token = auth_header
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]
    elif token.startswith("bearer "):
        token = token[len("bearer "):]

    if token != api_key:
        # Don't reveal what the correct key is
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── App lifecycle ──────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Check Jina Reader connectivity at startup."""
    jina_url = os.getenv("JINA_BASE_URL", "http://raspberrypi2:7262")
    healthy, msg = await check_health()
    if healthy:
        logger.info("Jina Reader connected at %s", jina_url)
    else:
        logger.warning("Jina Reader at %s unreachable: %s", jina_url, msg)
    yield


app = FastAPI(
    title="Jina → Firecrawl Bridge",
    description="Translate Jina AI Reader responses to Firecrawl API format",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Error handlers ─────────────────────────────────────────────────────


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": f"Validation error: {exc.errors()}"},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )


# ── Middleware ─────────────────────────────────────────────────────────


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Inject auth check for all API routes except health."""
    path = request.url.path
    if (path.startswith("/v1/") or path.startswith("/v2/")) and not path.endswith("/health"):
        try:
            _check_auth(request)
        except HTTPException:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Unauthorized"},
            )
    return await call_next(request)


# ── Routes ─────────────────────────────────────────────────────────────


@app.get("/v1/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check — verifies Jina Reader connectivity."""
    jina_url = os.getenv("JINA_BASE_URL", "http://raspberrypi2:7262")
    healthy, msg = await check_health()
    return HealthResponse(
        status="ok" if healthy else "degraded",
        jina_url=jina_url,
        jina_status=msg,
    )


@app.post("/v1/scrape", response_model=ScrapeResponse)
async def scrape(body: ScrapeRequest) -> ScrapeResponse:
    """Firecrawl-compatible scrape — translates to Jina Reader."""
    target_url = body.url

    if not target_url:
        return ScrapeResponse(
            success=False,
            error="No URL provided",
        )

    logger.info("Scrape request: %s (formats=%s)", target_url, body.formats or ["markdown"])

    result = await extract_url(target_url)

    if result.is_error:
        return ScrapeResponse(
            success=False,
            error=result.error,
        )

    # Build Firecrawl-compatible response
    metadata = ScrapeMetadata(
        title=result.title,
        description="",
        language="",
        sourceURL=result.source_url,
    )

    data = ScrapeData(
        markdown=result.content,
        metadata=metadata,
    )

    return ScrapeResponse(success=True, data=data)


@app.post("/v1/crawl", response_model=CrawlResponse)
async def crawl(body: CrawlRequest) -> CrawlResponse:
    """Stub crawl — immediately returns a fake job ID.

    Firecrawl's crawl is async (start crawl, then poll status).
    This stub returns immediately; the status endpoint always
    returns 'completed' with a single-page result.
    """
    logger.info("Crawl request (stub): %s", body.url)
    return CrawlResponse(
        success=True,
        id=f"jina-stub-{hash(body.url) & 0xFFFFFFFF}",
        url=body.url,
    )


@app.get("/v1/crawl/{crawl_id}", response_model=CrawlStatusResponse)
async def crawl_status(crawl_id: str) -> CrawlStatusResponse:
    """Stub crawl status — always completed with a placeholder.

    In a real Firecrawl backend, you'd poll this endpoint to check
    crawl progress. This stub returns immediate success.
    """
    return CrawlStatusResponse(
        success=True,
        status="completed",
    )


# ── V2 Routes (same logic, different prefix for SDK v4+) ────────────────


@app.get("/v2/health", response_model=HealthResponse)
async def health_v2() -> HealthResponse:
    return await health()


@app.post("/v2/scrape", response_model=ScrapeResponse)
async def scrape_v2(body: ScrapeRequest) -> ScrapeResponse:
    return await scrape(body)


@app.post("/v2/crawl", response_model=CrawlResponse)
async def crawl_v2(body: CrawlRequest) -> CrawlResponse:
    return await crawl(body)


@app.get("/v2/crawl/{crawl_id}", response_model=CrawlStatusResponse)
async def crawl_status_v2(crawl_id: str) -> CrawlStatusResponse:
    return await crawl_status(crawl_id)


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    """Run the bridge server with uvicorn."""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3838"))

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        log_level=log_level.lower(),
    )


if __name__ == "__main__":
    main()
