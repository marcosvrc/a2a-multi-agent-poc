# a2a-multi-agent-poc

POC multiagente distribuída: agentes em frameworks/linguagens diferentes
interoperando por **A2A** (Agent-to-Agent) e consumindo ferramentas por
**MCP** (Model Context Protocol). Caso de uso: planejador de viagens.

Especificação completa: [`a2a-multi-agent-poc-PROJECT_SPEC.md`](./a2a-multi-agent-poc-PROJECT_SPEC.md).

## Status: Fase 5 — Budget Agent real (CrewAI)

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
- **Budget Agent** (`agents/budget-crewai`, CrewAI / Python): combina os
  resultados de voo/hotel/atividade (não busca nada) em um total via
  `mcp-currency` + `mcp-calculator`, skills A2A `calculate_budget`/
  `optimize_budget`. Caminho determinístico por padrão (grátis); caminho
  guiado por CrewAI opcional com `CREWAI_LLM_MODEL` (ver ADR-012). É o
  único especialista delegado depois (não junto) dos outros três, já que
  precisa dos resultados deles, não do pedido bruto.
- **MCP Places** (`mcp/places`): servidor MCP com a tool `search_places`,
  dados mock determinísticos, priorizados por `preferences`.
- **MCP Weather** (`mcp/weather`): servidor MCP com a tool `get_weather`,
  previsão mock determinística local (§5.4 "poderá usar mock local").
- **MCP Currency** (`mcp/currency`): servidor MCP com a tool
  `convert_currency`, tabela de câmbio fixa e ilustrativa.
- **MCP Calculator** (`mcp/calculator`): servidor MCP com as tools `sum`/
  `subtract`/`multiply`/`divide` — sem `eval`, por exigência do spec.
- **Mock Specialist Agent** (`agents/mock-specialist`): agente A2A trivial,
  mantido para validar o protocolo independentemente dos especialistas.
- **Agent Registry** (`infrastructure/registry`): diretório de agentes.
- **OpenTelemetry + Jaeger** (`infrastructure/observability`): tracing
  distribuído (agentes Python via gRPC/4317, Hotel Agent via HTTP/4318).
- **Contratos compartilhados** (`contracts/`): JSON Schemas de
  `TravelRequest`/`TravelResponse` e resultados por especialista.

Com os quatro especialistas centrais reais (flight/hotel/activity/
budget), o Planner agora pode retornar `status: COMPLETED` (antes sempre
`PARTIAL`). Só o AWS Enrichment Agent **ainda não foi implementado** —
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
- Budget Agent: http://localhost:8005
- Mock Specialist Agent: http://localhost:8099
- MCP Flight Search: http://localhost:9001
- MCP Hotel Search: http://localhost:9002
- MCP Places: http://localhost:9003
- MCP Weather: http://localhost:9004
- MCP Currency: http://localhost:9005
- MCP Calculator: http://localhost:9006
- Agent Registry: http://localhost:8080
- Jaeger UI: http://localhost:16686

Teste rápido:

```bash
./scripts/smoke-test.sh
```

Envie uma solicitação de viagem (agora com voos, hotéis, roteiro de
atividades e orçamento calculado, todos reais):

```bash
curl -X POST http://localhost:8001/v1/travel-requests \
  -H 'Content-Type: application/json' \
  -d @contracts/examples/travel-request.example.json
```

Com os quatro especialistas centrais respondendo `SUCCESS`, a resposta
inclui `status: COMPLETED` — `flight`, `hotel`, `activities` e `budget`
todos `SUCCESS`, `budget.budget_status` classificado entre
`WITHIN_BUDGET`/`NEAR_LIMIT`/`OVER_BUDGET`. `enrichment` continua
`SKIPPED` (AWS opcional, desligado por padrão).

Mais detalhes em `docs/local-development.md` e `docs/testing.md`.

## Próximo passo recomendado

Fase 6 do spec (§43): paralelismo real entre os especialistas no
Planner (hoje a delegação é sequencial), sem alterar os contratos A2A/
Registry já validados.
