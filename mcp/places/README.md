# mcp-places

Servidor MCP (Streamable HTTP, `/mcp`) com uma tool: `search_places`.
Consumido pelo `activity-agent` (`agents/activity-beeai`).

## Tool

```json
{
  "destination": "Florianopolis",
  "preferences": ["beach"],
  "limit": 10
}
```

Retorna até `limit` pontos de interesse mock determinísticos (mesma
entrada → mesma saída), conforme `PROJECT_SPEC.md` §23 e §31. Quando
`preferences` combina com categorias conhecidas (`sightseeing`, `museum`,
`beach`, `hiking`, `food`, `shopping`, `nightlife`, `culture`), essas
categorias são priorizadas primeiro.

## Endpoints

- `GET /health`, `GET /ready`
- `POST /mcp` (MCP Streamable HTTP)

## Rodando localmente

```bash
pip install -r requirements.txt
python -m app.server
```
