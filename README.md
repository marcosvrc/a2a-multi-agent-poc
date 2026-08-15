# a2a-multi-agent-poc

POC multiagente distribuída: agentes em frameworks/linguagens diferentes
interoperando por **A2A** (Agent-to-Agent) e consumindo ferramentas por
**MCP** (Model Context Protocol). Caso de uso: planejador de viagens.

Especificação completa: [`a2a-multi-agent-poc-PROJECT_SPEC.md`](./a2a-multi-agent-poc-PROJECT_SPEC.md).

## Status: Fase 2 — Flight Agent real

Implementado até aqui (ver `docs/architecture.md` para detalhes):

- **Planner Agent** (`agents/planner-adk`, Google ADK / Python): descoberta
  dinâmica de agentes via Agent Registry, delegação via A2A, consolidação
  de resposta com as regras de degradação do spec.
- **Flight Agent** (`agents/flight-openai`, OpenAI Agents SDK / Python):
  busca e ranqueia voos via `mcp-flight-search`, skill A2A `search_flights`.
  Caminho determinístico por padrão (grátis); caminho guiado por LLM
  opcional com `OPENAI_API_KEY` (ver ADR-009).
- **MCP Flight Search** (`mcp/flight-search`): servidor MCP com a tool
  `search_flights`, dados mock determinísticos.
- **Mock Specialist Agent** (`agents/mock-specialist`): agente A2A trivial,
  mantido para validar o protocolo independentemente dos especialistas.
- **Agent Registry** (`infrastructure/registry`): diretório de agentes.
- **OpenTelemetry + Jaeger** (`infrastructure/observability`): tracing
  distribuído.
- **Contratos compartilhados** (`contracts/`): JSON Schemas de
  `TravelRequest`/`TravelResponse` e resultados por especialista.

Hotel, Activity, Budget e AWS Enrichment **ainda não foram implementados**
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
- Mock Specialist Agent: http://localhost:8099
- MCP Flight Search: http://localhost:9001
- Agent Registry: http://localhost:8080
- Jaeger UI: http://localhost:16686

Teste rápido:

```bash
./scripts/smoke-test.sh
```

Envie uma solicitação de viagem (agora com voos reais do `flight-agent`):

```bash
curl -X POST http://localhost:8001/v1/travel-requests \
  -H 'Content-Type: application/json' \
  -d @contracts/examples/travel-request.example.json
```

A resposta traz `flight.status = SUCCESS` com até 5 opções ranqueadas por
preço; `hotel`, `activities` e `budget` continuam `UNAVAILABLE`/`UNKNOWN`
até as próximas fases.

Mais detalhes em `docs/local-development.md` e `docs/testing.md`.

## Próximo passo recomendado

Fase 3 do spec (§43): implementar o **Hotel Agent** real (LangGraph em
TypeScript + A2A + MCP Hotel Search) — primeiro agente não-Python da POC,
sem alterar os contratos A2A/Registry já validados.
