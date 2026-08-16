# a2a-multi-agent-poc

POC multiagente distribuída: agentes em frameworks/linguagens diferentes
interoperando por **A2A** (Agent-to-Agent) e consumindo ferramentas por
**MCP** (Model Context Protocol). Caso de uso: planejador de viagens.

Especificação completa: [`a2a-multi-agent-poc-PROJECT_SPEC.md`](./a2a-multi-agent-poc-PROJECT_SPEC.md).

## Status: Fase 4 — Activity Agent real (BeeAI)

Implementado até aqui (ver `docs/architecture.md` para detalhes):

- **Planner Agent** (`agents/planner-adk`, Google ADK / Python): descoberta
  dinâmica de agentes via Agent Registry, delegação via A2A, consolidação
  de resposta com as regras de degradação do spec.
- **Flight Agent** (`agents/flight-openai`, OpenAI Agents SDK / Python):
  busca e ranqueia voos via `mcp-flight-search`, skill A2A `search_flights`.
  Caminho determinístico por padrão (grátis); caminho guiado por LLM
  opcional com `OPENAI_API_KEY` (ver ADR-009).
- **Hotel Agent** (`agents/hotel-langgraph`, LangGraph / TypeScript):
  primeiro agente não-Python da POC. Fluxo com estado
  (`parse_request → search_hotels → filter_results → rank_results →
  build_response`) via `mcp-hotel-search`, skill A2A `search_hotels`. O
  adapter A2A é uma reimplementação própria em TypeScript, espelhando o
  contrato de wire do adapter Python (ver ADR-010) — prova de
  interoperabilidade real entre linguagens.
- **Activity Agent** (`agents/activity-beeai`, BeeAI Framework / Python):
  monta roteiro diário via `mcp-places` (+ `mcp-weather` quando
  disponível), skills A2A `plan_activities`/`optimize_itinerary`.
  Caminho determinístico por padrão (grátis); caminho guiado por BeeAI
  opcional com `BEEAI_CHAT_MODEL` (ver ADR-011). Falha do MCP Weather
  nunca bloqueia o roteiro (§5.4/CT-R03).
- **MCP Flight Search** (`mcp/flight-search`): servidor MCP com a tool
  `search_flights`, dados mock determinísticos.
- **MCP Hotel Search** (`mcp/hotel-search`): servidor MCP com a tool
  `search_hotels`, dados mock determinísticos.
- **MCP Places** (`mcp/places`): servidor MCP com a tool `search_places`,
  dados mock determinísticos, priorizados por `preferences`.
- **MCP Weather** (`mcp/weather`): servidor MCP com a tool `get_weather`,
  previsão mock determinística local (§5.4 "poderá usar mock local").
- **Mock Specialist Agent** (`agents/mock-specialist`): agente A2A trivial,
  mantido para validar o protocolo independentemente dos especialistas.
- **Agent Registry** (`infrastructure/registry`): diretório de agentes.
- **OpenTelemetry + Jaeger** (`infrastructure/observability`): tracing
  distribuído (agentes Python via gRPC/4317, Hotel Agent via HTTP/4318).
- **Contratos compartilhados** (`contracts/`): JSON Schemas de
  `TravelRequest`/`TravelResponse` e resultados por especialista.

Budget e AWS Enrichment **ainda não foram implementados** —
propositalmente, seguindo a regra do spec de não implementar tudo de uma
vez (§42) e a ordem recomendada em §43.

## Rodando

```bash
cp .env.example .env
make local
# ou: docker compose up --build
```

- Planner: http://localhost:8001
- Flight Agent: http://localhost:8002
- Hotel Agent: http://localhost:8003
- Activity Agent: http://localhost:8004
- Mock Specialist Agent: http://localhost:8099
- MCP Flight Search: http://localhost:9001
- MCP Hotel Search: http://localhost:9002
- MCP Places: http://localhost:9003
- MCP Weather: http://localhost:9004
- Agent Registry: http://localhost:8080
- Jaeger UI: http://localhost:16686

Teste rápido:

```bash
./scripts/smoke-test.sh
```

Envie uma solicitação de viagem (agora com voos, hotéis e roteiro de
atividades reais):

```bash
curl -X POST http://localhost:8001/v1/travel-requests \
  -H 'Content-Type: application/json' \
  -d @contracts/examples/travel-request.example.json
```

A resposta traz `flight.status = SUCCESS`, `hotel.status = SUCCESS` e
`activities.status = SUCCESS` (um roteiro diário, um dia por data da
viagem); `budget` continua `UNKNOWN` até a próxima fase.

Mais detalhes em `docs/local-development.md` e `docs/testing.md`.

## Próximo passo recomendado

Fase 5 do spec (§43): implementar o **Budget Agent** (CrewAI / Python +
MCP Currency + MCP Calculator), sem alterar os contratos A2A/Registry já
validados.
