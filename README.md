# a2a-multi-agent-poc

POC multiagente distribuída: agentes em frameworks/linguagens diferentes
interoperando por **A2A** (Agent-to-Agent) e consumindo ferramentas por
**MCP** (Model Context Protocol). Caso de uso: planejador de viagens.

Especificação completa: [`a2a-multi-agent-poc-PROJECT_SPEC.md`](./a2a-multi-agent-poc-PROJECT_SPEC.md).

## Status: Fase 3 — Hotel Agent real (TypeScript)

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
- **MCP Flight Search** (`mcp/flight-search`): servidor MCP com a tool
  `search_flights`, dados mock determinísticos.
- **MCP Hotel Search** (`mcp/hotel-search`): servidor MCP com a tool
  `search_hotels`, dados mock determinísticos.
- **Mock Specialist Agent** (`agents/mock-specialist`): agente A2A trivial,
  mantido para validar o protocolo independentemente dos especialistas.
- **Agent Registry** (`infrastructure/registry`): diretório de agentes.
- **OpenTelemetry + Jaeger** (`infrastructure/observability`): tracing
  distribuído (agentes Python via gRPC/4317, Hotel Agent via HTTP/4318).
- **Contratos compartilhados** (`contracts/`): JSON Schemas de
  `TravelRequest`/`TravelResponse` e resultados por especialista.

Activity, Budget e AWS Enrichment **ainda não foram implementados**
— propositalmente, seguindo a regra do spec de não implementar tudo de uma
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
- Mock Specialist Agent: http://localhost:8099
- MCP Flight Search: http://localhost:9001
- MCP Hotel Search: http://localhost:9002
- Agent Registry: http://localhost:8080
- Jaeger UI: http://localhost:16686

Teste rápido:

```bash
./scripts/smoke-test.sh
```

Envie uma solicitação de viagem (agora com voos e hotéis reais):

```bash
curl -X POST http://localhost:8001/v1/travel-requests \
  -H 'Content-Type: application/json' \
  -d @contracts/examples/travel-request.example.json
```

A resposta traz `flight.status = SUCCESS` e `hotel.status = SUCCESS`, cada
um com até 5 opções ranqueadas; `activities` e `budget` continuam
`UNAVAILABLE`/`UNKNOWN` até as próximas fases.

Mais detalhes em `docs/local-development.md` e `docs/testing.md`.

## Próximo passo recomendado

Fase 4 do spec (§43): implementar o **Activity Agent** (BeeAI / Python +
MCP Places + MCP Weather), sem alterar os contratos A2A/Registry já
validados.
