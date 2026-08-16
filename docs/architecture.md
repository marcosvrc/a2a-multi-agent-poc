# Arquitetura — Estado atual (Fase 4)

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
  ├─A2A──▶ Hotel Agent (LangGraph, TypeScript, :8003)
  │            │  MCP
  │            ▼
  │         mcp-hotel-search (:9002)
  │
  └─A2A──▶ Activity Agent (BeeAI Framework, Python, :8004)
               │  MCP
               ├────▶ mcp-places (:9003)
               └────▶ mcp-weather (:9004)
```

Componentes:

- **planner-agent** (`agents/planner-adk`): orquestrador. Descobre agentes
  via `agent-registry`, delega via A2A, aplica as regras de degradação do
  §11 para capacidades ainda não implementadas, consolida `TravelResponse`.
  Já parseia os resultados reais de `flight-agent`, `hotel-agent` e
  `activity-agent` (parser genérico `_parse_specialist_result`,
  compartilhado pelos três).
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
- **activity-agent** (`agents/activity-beeai`): especialista de
  atividades. Caminho determinístico por padrão (chama `mcp-places` uma
  vez e `mcp-weather` por dia, monta roteiro sem conflitos de horário,
  grátis); caminho guiado por BeeAI Framework opcional com
  `BEEAI_CHAT_MODEL` (ADR-011). Skills A2A `plan_activities` /
  `optimize_itinerary`. Falha do MCP Weather nunca bloqueia o roteiro —
  apenas aquele dia fica com `weather: null` (§5.4/CT-R03).
- **mcp-flight-search** (`mcp/flight-search`): servidor MCP (Streamable
  HTTP) com a tool `search_flights`, dados mock determinísticos (§23/§31).
- **mcp-hotel-search** (`mcp/hotel-search`): servidor MCP (Streamable
  HTTP) com a tool `search_hotels`, dados mock determinísticos (§23/§31).
- **mcp-places** (`mcp/places`): servidor MCP (Streamable HTTP) com a tool
  `search_places`, dados mock determinísticos, priorizados por
  `preferences` (§23/§31).
- **mcp-weather** (`mcp/weather`): servidor MCP (Streamable HTTP) com a
  tool `get_weather`, previsão mock local determinística (§5.4/§23).
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

- Budget / AWS Enrichment agents (Fases 5 e 7).
- Servidores MCP restantes (`mcp/currency`, `mcp/calculator`) — Fase 5.
- Segurança JWT/OAuth (Fase 9) — hoje `AUTH_MODE=dev`, sem token real.
- Resiliência avançada (circuit breaker) — Fase 8. Timeout básico via
  `httpx`/`fetch` já existe nos clientes A2A/Registry/MCP; degradação
  por-dia do MCP Weather (CT-R03) já implementada no Activity Agent.
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
