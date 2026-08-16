# mcp-weather

Servidor MCP (Streamable HTTP, `/mcp`) com uma tool: `get_weather`.
Consumido pelo `activity-agent` (`agents/activity-beeai`).

## Tool

```json
{
  "destination": "Florianopolis",
  "date": "2026-09-21"
}
```

Retorna previsão mock determinística (mesma entrada → mesma saída),
conforme `PROJECT_SPEC.md` §23 e §5.4 ("O Weather MCP poderá usar mock
local"). Qualquer falha deve ser tratada pelo chamador como "sem
previsão disponível", nunca bloqueando o roteiro (§5.4).

## Endpoints

- `GET /health`, `GET /ready`
- `POST /mcp` (MCP Streamable HTTP)

## Rodando localmente

```bash
pip install -r requirements.txt
python -m app.server
```
