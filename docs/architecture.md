# Arquitetura — Estado atual (Fase 3)

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
  ├─A2A──▶ Flight Agent (OpenAI Agents SDK, Python, :8002)
  │            │  MCP
  │            ▼
  │         mcp-flight-search (:9001)
  │
  └─A2A──▶ Hotel Agent (LangGraph, TypeScript, :8003)
               │  MCP
               ▼
            mcp-hotel-search (:9002)
```

Componentes:

- **planner-agent** (`agents/planner-adk`): orquestrador. Descobre agentes
  via `agent-registry`, delega via A2A, aplica as regras de degradação do
  §11 para capacidades ainda não implementadas, consolida `TravelResponse`.
  Já parseia os resultados reais de `flight-agent` e `hotel-agent` (parser
  genérico `_parse_specialist_result`, compartilhado entre os dois).
- **flight-agent** (`agents/flight-openai`): especialista de voos. Caminho
  determinístico por padrão (chama `mcp-flight-search`, ordena por preço,
  grátis); caminho guiado por LLM opcional com `OPENAI_API_KEY` via OpenAI
  Agents SDK (ADR-009). Skill A2A `search_flights`.
- **hotel-agent** (`agents/hotel-langgraph`): especialista de hotéis.
  Primeiro agente não-Python da POC. Fluxo com estado via LangGraph
  (`parse_request → search_hotels → filter_results → rank_results →
  build_response`, ver README do agente), chama `mcp-hotel-search`. Skill
  A2A `search_hotels`. O adapter A2A é uma reimplementação própria em
  TypeScript/Express, espelhando o contrato de wire do adapter Python
  (ADR-010) — não há biblioteca compartilhada entre os dois.
- **mcp-flight-search** (`mcp/flight-search`): servidor MCP (Streamable
  HTTP) com a tool `search_flights`, dados mock determinísticos (§23/§31).
- **mcp-hotel-search** (`mcp/hotel-search`): servidor MCP (Streamable
  HTTP) com a tool `search_hotels`, dados mock determinísticos (§23/§31).
- **mock-specialist-agent** (`agents/mock-specialist`): agente A2A trivial
  (skill `echo_ping`), mantido para validar o protocolo independentemente
  dos especialistas reais.
- **agent-registry** (`infrastructure/registry`): diretório didático de
  agentes (não substitui o Agent Card).
- **otel-collector + jaeger** (`infrastructure/observability`): tracing
  distribuído. Agentes Python exportam via gRPC (`:4317`); o Hotel Agent
  (Node.js) exporta via HTTP (`:4318`) — ambos os protocolos suportados
  pelo mesmo collector.

## Ainda não implementado

- Activity / Budget / AWS Enrichment agents (Fases 4-5 e 7).
- Servidores MCP restantes (`mcp/places`, `mcp/weather`, `mcp/currency`,
  `mcp/calculator`) — Fases 4-5.
- Segurança JWT/OAuth (Fase 9) — hoje `AUTH_MODE=dev`, sem token real.
- Resiliência avançada (circuit breaker) — Fase 8. Timeout básico via
  `httpx`/`fetch` já existe nos clientes A2A/Registry/MCP.
- `docker-compose.aws.yml` e profile `aws` — Fase 7.
- Paralelismo real entre especialistas no Planner — hoje a delegação é
  sequencial; paralelismo é Fase 6.

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
