# Arquitetura — Estado atual (Fase 2)

Ver `a2a-multi-agent-poc-PROJECT_SPEC.md` na raiz do repositório para a
especificação completa. Este documento descreve apenas o que já foi
implementado.

## Implementado

```text
User (HTTP)
  │
  ▼
Planner Agent (Google ADK scaffold, Python, :8001)
  │  descobre via
  ▼
Agent Registry (:8080)
  │
  ├─A2A──▶ Mock Specialist Agent (:8099)
  │
  └─A2A──▶ Flight Agent (OpenAI Agents SDK, Python, :8002)
              │  MCP
              ▼
           mcp-flight-search (:9001)
```

Componentes:

- **planner-agent** (`agents/planner-adk`): orquestrador. Descobre agentes
  via `agent-registry`, delega via A2A, aplica as regras de degradação do
  §11 para capacidades ainda não implementadas, consolida `TravelResponse`.
  Já parseia o `FlightResult` real vindo do `flight-agent`.
- **flight-agent** (`agents/flight-openai`): especialista de voos. Caminho
  determinístico por padrão (chama `mcp-flight-search`, ordena por preço,
  grátis); caminho guiado por LLM opcional com `OPENAI_API_KEY` via OpenAI
  Agents SDK (ADR-009). Skill A2A `search_flights`.
- **mcp-flight-search** (`mcp/flight-search`): servidor MCP (Streamable
  HTTP) com a tool `search_flights`, dados mock determinísticos (§23/§31).
- **mock-specialist-agent** (`agents/mock-specialist`): agente A2A trivial
  (skill `echo_ping`), mantido para validar o protocolo independentemente
  dos especialistas reais.
- **agent-registry** (`infrastructure/registry`): diretório didático de
  agentes (não substitui o Agent Card).
- **otel-collector + jaeger** (`infrastructure/observability`): tracing
  distribuído.

## Ainda não implementado

- Hotel / Activity / Budget / AWS Enrichment agents (Fases 3-5 e 7).
- Servidores MCP restantes (`mcp/hotel-search`, `mcp/places`,
  `mcp/weather`, `mcp/currency`, `mcp/calculator`) — Fases 3-5.
- Segurança JWT/OAuth (Fase 9) — hoje `AUTH_MODE=dev`, sem token real.
- Resiliência avançada (circuit breaker) — Fase 8. Timeout básico via
  `httpx` já existe nos clientes A2A/Registry/MCP.
- `docker-compose.aws.yml` e profile `aws` — Fase 7.

## Protocolo × responsabilidade (PROJECT_SPEC.md §49)

```text
A2A       = Agent ↔ Agent
MCP       = Agent ↔ Tool / API / Data
HTTP      = transporte
JSON-RPC  = binding quando aplicável
SSE       = streaming (não implementado nesta milestone)
OTel      = observabilidade
Docker    = runtime local
```
