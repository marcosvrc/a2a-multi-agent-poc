# activity-agent

Especialista em atividades (BeeAI Framework, Python), conforme
`PROJECT_SPEC.md` §5.4.

## Escopo

Monta um roteiro diário para as datas da viagem, respeitando:

- duração da viagem (um dia por data entre `start_date` e `end_date`,
  limitado a `ACTIVITY_MAX_DAYS`, padrão 14);
- ausência de conflito de horários (2 atividades por dia, em horários
  fixos não sobrepostos: `09:00`, `14:00`);
- preferências do viajante (categorias combinadas em `preferences` são
  priorizadas na busca via MCP Places);
- clima quando disponível, mas nunca bloqueia o roteiro se o MCP Weather
  falhar (§5.4 "permitir execução sem informação meteorológica" /
  CT-R03 — nesse caso `weather` fica `null` só para o dia afetado).

## Dois caminhos de execução

- **Determinístico (padrão, sem `BEEAI_CHAT_MODEL`)**: chama
  `mcp-places` uma vez, `mcp-weather` uma vez por dia, monta o roteiro
  com uma heurística fixa de distribuição. É o caminho testado
  automaticamente e o que roda em `docker compose up` sem custo.
- **Guiado por BeeAI (`BEEAI_CHAT_MODEL` setada)**: usaria
  `beeai_framework.agents.react.ReActAgent` com os MCPs de Places/Weather
  como tools. Ver ADR-011. Não é exercitado pelos testes automatizados
  desta milestone (nenhum backend de chat disponível no ambiente de
  desenvolvimento); qualquer falha nesse caminho cai automaticamente para
  o determinístico.

Nunca inventa lugares ou previsão (§31): toda opção retornada vem de uma
chamada real a `search_places`/`get_weather` via MCP.

## Skills

```text
plan_activities
optimize_itinerary
```

`plan_activities` é a skill exercitada por este milestone (o Planner
delega o `TravelRequest` inteiro, como faz com flight-agent e
hotel-agent). `optimize_itinerary` está declarada no Agent Card para
refletir §5.4, mas não tem lógica própria ainda — hoje o roteiro já sai
sem conflitos do caminho determinístico.

## Endpoints

- `GET /health`, `GET /ready`
- `GET /.well-known/agent-card.json`
- `POST /a2a` (A2A JSON-RPC, mesmo adapter dos outros agentes Python)

## Rodando localmente

```bash
pip install -e .
uvicorn app.main:app --reload --port 8004
```

## Testes

```bash
pip install -e . pytest
pytest -q
```
