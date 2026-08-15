# mock-specialist-agent

Agente A2A trivial, criado apenas para validar o fluxo A2A ponta-a-ponta
(Agent Card, `message/send`, `Task`) antes de implementar os cinco
especialistas reais, conforme `PROJECT_SPEC.md` §43 (Fase 1) e §51 (M1).

## Rodando localmente

```bash
pip install -e .
uvicorn app.main:app --reload --port 8099
```

## Endpoints

- `GET /health`
- `GET /ready`
- `GET /.well-known/agent-card.json`
- `POST /a2a` (JSON-RPC 2.0: `message/send`, `tasks/get`, `tasks/cancel`)

## Skill

- `echo_ping`: ecoa o texto recebido, prefixado, para provar o round-trip A2A.
