"""Jina → Firecrawl Bridge — Pydantic models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Firecrawl scrape request ──────────────────────────────────────────


class ScrapeRequest(BaseModel):
    """Firecrawl-compatible scrape request body."""

    url: str = Field(..., description="The URL to scrape")
    formats: Optional[List[str]] = Field(
        default=["markdown"],
        description="Output formats (markdown, html, screenshot, etc.)",
    )
    onlyMainContent: Optional[bool] = Field(
        default=True,
        description="Only return the main content of the page",
    )
    timeout: Optional[int] = Field(
        default=None,
        description="Timeout in milliseconds",
    )

    class Config:
        extra = "ignore"  # tolerate other Firecrawl fields


# ── Firecrawl scrape response ─────────────────────────────────────────


class ScrapeMetadata(BaseModel):
    """Metadata extracted from the scraped page."""

    title: str = ""
    description: str = ""
    language: str = ""
    sourceURL: Optional[str] = None


class ScrapeData(BaseModel):
    """Scraped content in requested formats."""

    markdown: Optional[str] = None
    html: Optional[str] = None
    metadata: ScrapeMetadata = Field(default_factory=ScrapeMetadata)


class ScrapeResponse(BaseModel):
    """Firecrawl-compatible scrape response."""

    success: bool = True
    data: Optional[ScrapeData] = None
    error: Optional[str] = None


# ── Crawl (stub) ──────────────────────────────────────────────────────


class CrawlRequest(BaseModel):
    """Firecrawl-compatible crawl request body."""

    url: str
    maxPages: Optional[int] = 1

    class Config:
        extra = "ignore"


class CrawlResponse(BaseModel):
    """Stub crawl response — immediately returns a fake job ID."""

    success: bool = True
    id: str = "stub-crawl-id"
    url: str = ""
    error: Optional[str] = None


class CrawlStatusResponse(BaseModel):
    """Stub crawl status — always 'completed' with the scrape result."""

    success: bool = True
    status: str = "completed"
    data: Optional[List[ScrapeData]] = None
    error: Optional[str] = None


# ── Health ─────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    jina_url: str
    jina_status: str
    version: str = "1.0.0"
