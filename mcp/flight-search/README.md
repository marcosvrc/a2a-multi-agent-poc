# mcp-flight-search

Servidor MCP (Streamable HTTP, `/mcp`) com uma tool: `search_flights`.
Consumido pelo `flight-agent` (`agents/flight-openai`).

## Tool

```json
{
  "origin": "GRU",
  "destination": "FLN",
  "start_date": "2026-09-20",
  "end_date": "2026-09-24",
  "travelers": 2
}
```

Retorna até 5 voos mock determinísticos (mesma entrada → mesma saída),
conforme `PROJECT_SPEC.md` §23 e §31 (nunca inventar preço fora da
ferramenta).

## Endpoints

- `GET /health`, `GET /ready`
- `POST /mcp` (MCP Streamable HTTP)

## Rodando localmente

```bash
pip install -r requirements.txt
python -m app.server
```
