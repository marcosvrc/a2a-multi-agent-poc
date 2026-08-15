# agent-registry

Serviço didático de diretório de agentes. Não substitui o Agent Card A2A
(`/.well-known/agent-card.json`), apenas informa ao Planner quais agentes
existem, onde estão e se são obrigatórios.

## Endpoints

- `GET /health`
- `GET /ready`
- `GET /agents`
- `GET /agents/{agent_id}`
- `GET /agents/{agent_id}/health`

## Rodando localmente

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

A lista de agentes é lida de `agents.json` (path configurável via `REGISTRY_FILE`).
