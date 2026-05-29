# Jina → Firecrawl Bridge

A lightweight translation layer that exposes **Jina AI Reader** (self-hosted OSS) through a **Firecrawl-compatible API**.

Drop it in front of any tool that expects a Firecrawl backend (like Hermes Agent, LangChain, etc.) and it'll transparently route requests through Jina Reader instead.

```
┌─────────────┐     Firecrawl API     ┌──────────────────┐     Jina Reader      ┌─────────────┐
│ Your Tool   │ ─── POST /v1/scrape → │  jina-firecrawl  │ ── GET /:url ─────→ │ Jina Reader │
│ (Hermes,    │ ←── Firecrawl JSON ───│  Bridge           │ ←── Markdown ────── │ OSS:7262   │
│  LangChain) │                       │  :3838            │                     └─────────────┘
└─────────────┘                       └──────────────────┘
```

## Quick Start

```bash
docker compose up -d
```

The bridge will be available at `http://localhost:3838`.

Now point any Firecrawl-compatible client to this bridge:

```bash
# Instead of https://api.firecrawl.dev, use:
curl -X POST http://localhost:3838/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "formats": ["markdown"]}'
```

## Usage with Hermes Agent

Configure Hermes to use this bridge:

```yaml
# ~/.hermes/config.yaml
web:
  extract_backend: firecrawl

# env:
FIRECRAWL_API_URL=http://localhost:3838
FIRECRAWL_API_KEY=jina-bridge  # any non-empty value, the bridge doesn't enforce auth by default
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `JINA_BASE_URL` | `http://raspberrypi2:7262` | Jina Reader endpoint |
| `HOST` | `0.0.0.0` | Listen address |
| `PORT` | `3838` | Listen port |
| `JINA_TIMEOUT` | `60` | Jina Reader request timeout (seconds) |
| `BRIDGE_API_KEY` | (empty) | If set, clients must pass `Authorization: Bearer <key>` |
| `LOG_LEVEL` | `info` | Logging level |

## API Endpoints

### `POST /v1/scrape`

Firecrawl-compatible scrape endpoint. See [Firecrawl API docs](https://docs.firecrawl.dev/api-reference/endpoint/scrape).

Request:
```json
{
  "url": "https://example.com",
  "formats": ["markdown"],
  "onlyMainContent": true
}
```

Response:
```json
{
  "success": true,
  "data": {
    "markdown": "# Page content in markdown...",
    "metadata": {
      "title": "Example Domain",
      "sourceURL": "https://example.com",
      "description": "",
      "language": "en"
    }
  }
}
```

### `GET /v1/health`

Health check — returns `{"status": "ok", "jina_status": "connected"}`.

### `POST /v1/crawl` (stub)

Returns immediately — useful for tools that probe crawl availability.

## How It Works

1. Receives a Firecrawl-format scrape request
2. Extracts the target URL and options
3. Calls Jina Reader: `GET {JINA_BASE_URL}/{target_url}`
4. Parses the Jina Response (Title / URL Source / Markdown Content sections)
5. Returns the content in Firecrawl's JSON response format

## Deployment

### Docker Compose (recommended)

```yaml
services:
  bridge:
    build: .
    ports:
      - "3838:3838"
    environment:
      JINA_BASE_URL: http://raspberrypi2:7262
    restart: unless-stopped
```

### Standalone (Python)

```bash
pip install fastapi uvicorn httpx
python src/main.py
```

## License

MIT
