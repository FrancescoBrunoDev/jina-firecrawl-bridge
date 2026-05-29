"""Jina Reader HTTP client — async, with proper error handling."""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Default Jina Reader OSS endpoint
_DEFAULT_JINA_URL = "http://raspberrypi2:7262"
_DEFAULT_TIMEOUT = 60


def _get_jina_url() -> str:
    """Return configured Jina Reader base URL."""
    return (os.getenv("JINA_BASE_URL") or _DEFAULT_JINA_URL).rstrip("/")


def _get_timeout() -> int:
    """Return configured request timeout."""
    raw = os.getenv("JINA_TIMEOUT", str(_DEFAULT_TIMEOUT))
    try:
        return max(5, int(raw))
    except (ValueError, TypeError):
        return _DEFAULT_TIMEOUT


class JinaResult:
    """Parsed result from a Jina Reader response."""

    def __init__(
        self,
        title: str = "",
        content: str = "",
        source_url: str = "",
        error: Optional[str] = None,
    ):
        self.title = title
        self.content = content
        self.source_url = source_url
        self.error = error

    @property
    def is_error(self) -> bool:
        return self.error is not None


def parse_jina_response(raw_text: str, request_url: str) -> JinaResult:
    """Parse Jina Reader's text response format.

    Jina returns::

        Title: Example Domain
        URL Source: https://example.com/
        Markdown Content:
        <actual content>

    Args:
        raw_text: The raw text response from Jina Reader.
        request_url: The original URL that was requested (for error reporting).

    Returns:
        A JinaResult with parsed title and content.
    """
    if not raw_text or not raw_text.strip():
        return JinaResult(error="Empty response from Jina Reader")

    lines = raw_text.split("\n")

    title = ""
    source_url = ""
    content = raw_text  # fallback: whole response

    # Parse header lines (usually first 3-5 lines)
    for line in lines:
        if line.startswith("Title:"):
            title = line[len("Title:"):].strip()
        elif line.startswith("URL Source:"):
            source_url = line[len("URL Source:"):].strip()

    # Find the Markdown Content boundary
    md_marker = "Markdown Content:"
    md_idx = raw_text.find(md_marker)
    if md_idx != -1:
        content = raw_text[md_idx + len(md_marker):].strip()
    elif title or source_url:
        # Header present but no markdown marker — skip the header lines
        header_end = 0
        for i, line in enumerate(lines):
            if not line.strip() and i > 0:
                header_end = i + 1
                break
        if header_end > 0:
            content = "\n".join(lines[header_end:]).strip()

    if not content:
        return JinaResult(error="No content in Jina Reader response")

    return JinaResult(
        title=title or source_url or request_url,
        content=content,
        source_url=source_url or request_url,
    )


async def extract_url(target_url: str) -> JinaResult:
    """Extract a URL via Jina Reader.

    Args:
        target_url: The URL to extract (e.g., ``https://example.com``).

    Returns:
        A JinaResult with parsed content or error.
    """
    base = _get_jina_url()
    timeout_secs = _get_timeout()
    jina_request_url = f"{base}/{target_url}"

    logger.info(
        "Jina extract: %s → %s (timeout=%ds)",
        target_url,
        jina_request_url,
        timeout_secs,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_secs),
            follow_redirects=True,
        ) as client:
            resp = await client.get(jina_request_url)

        if resp.status_code >= 400:
            return JinaResult(
                error=f"Jina Reader returned HTTP {resp.status_code} for {target_url}"
            )

        return parse_jina_response(resp.text, target_url)

    except httpx.TimeoutException:
        return JinaResult(
            error=f"Jina Reader timed out after {timeout_secs}s for {target_url}"
        )
    except httpx.ConnectError as exc:
        return JinaResult(
            error=f"Jina Reader connection failed: {exc}"
        )
    except httpx.RequestError as exc:
        return JinaResult(
            error=f"Jina Reader request error: {exc}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error extracting %s", target_url)
        return JinaResult(error=f"Unexpected error: {exc}")


async def check_health() -> Tuple[bool, str]:
    """Check if Jina Reader is reachable.

    Returns:
        Tuple of (healthy: bool, message: str).
    """
    base = _get_jina_url()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(base)
        if resp.status_code < 500:
            return True, "connected"
        return False, f"HTTP {resp.status_code}"
    except httpx.ConnectError:
        return False, "connection refused"
    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as exc:
        return False, str(exc)
