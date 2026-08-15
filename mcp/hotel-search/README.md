# mcp-hotel-search

Servidor MCP (Streamable HTTP, `/mcp`) com uma tool: `search_hotels`.
Consumido pelo `hotel-agent` (`agents/hotel-langgraph`).

## Tool

```json
{
  "destination": "Florianopolis",
  "start_date": "2026-09-20",
  "end_date": "2026-09-24",
  "guests": 2
}
```

Retorna hotéis mock determinísticos (mesma entrada → mesma saída),
conforme `PROJECT_SPEC.md` §23 e §31.

## Endpoints

- `GET /health`, `GET /ready`
- `POST /mcp` (MCP Streamable HTTP)

## Rodando localmente

```bash
pip install -r requirements.txt
PORT=9002 python -m app.server
```
