# Arquitetura — Estado atual (Fase 7)

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
  ├─A2A──▶ Activity Agent (BeeAI Framework, Python, :8004)
  │            │  MCP
  │            ├────▶ mcp-places (:9003)
  │            └────▶ mcp-weather (:9004)
  │
  ├─A2A──▶ Budget Agent (CrewAI, Python, :8005)          [delegado depois do fan-out,
  │            │  MCP                                     recebe flight/hotel/
  │            ├────▶ mcp-currency (:9005)                 activity já resolvidos]
  │            └────▶ mcp-calculator (:9006)
  │
  └─A2A──▶ AWS Enrichment Agent (Strands, Python, :8006)   [opcional — só chamado se
               │  MCP                                      AWS_AGENT_ENABLED=true;
               └────▶ mcp-weather (:9004)                  delegado por último]
                    │  opcional
                    ▼
               Ollama (local) | Amazon Bedrock
```

Flight/Hotel/Activity são delegados concorrentemente; Budget é
sequenciado depois deles (precisa dos resultados); Enrichment é
sequenciado depois do Budget e só é tentado se ligado — ver "Paralelismo"
e "AWS Enrichment" abaixo.

Componentes:

- **planner-agent** (`agents/planner-adk`): orquestrador. Descobre agentes
  via `agent-registry` + Agent Card (seleção por *skill*, nunca por id
  hard-coded, §9), delega via A2A, consolida `TravelResponse`. Parseia os
  resultados reais dos cinco especialistas com um parser genérico
  (`_parse_specialist_result`) que também trata `task.status.state`
  (`failed`/`canceled` → `UNAVAILABLE` com o motivo; não-terminal →
  degrada em vez de mal-interpretar). O Budget Agent é delegado numa
  etapa própria (`_delegate_budget`), depois de flight/hotel/activity já
  parseados, pois recebe os *resultados* deles em vez do `TravelRequest`
  bruto (§5.5). O AWS Enrichment Agent é delegado numa etapa ainda mais
  separada (`_delegate_enrichment`), depois do Budget, e só é tentado
  quando `AWS_AGENT_ENABLED=true` (§5.6/§11) — em nenhum dos dois estados
  isso afeta `overall_status`. Com os quatro especialistas centrais
  `SUCCESS`, a resposta consolidada chega a `status: COMPLETED`; se
  nenhum tiver sucesso, `FAILED`; caso contrário, `PARTIAL`.
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
- **budget-agent** (`agents/budget-crewai`): especialista de orçamento.
  Não busca nada — combina os custos de voo/hotel/atividade (mais
  estimativas de comida/transporte) via `mcp-calculator`
  (`sum`/`subtract`/`multiply`, nunca `eval`) e, quando a moeda difere de
  BRL, `mcp-currency`. Caminho determinístico por padrão (grátis);
  caminho guiado por CrewAI opcional com `CREWAI_LLM_MODEL` (ADR-012).
  Skills A2A `calculate_budget` / `optimize_budget`.
- **aws-enrichment-agent** (`agents/aws-strands`): especialista de
  enriquecimento, totalmente **opcional** (§5.6) — comentário de clima
  (`mcp-weather`) e dicas curtas de destino. Nunca aprova/rejeita viagem,
  calcula orçamento ou escolhe voo/hotel. Caminho determinístico por
  padrão (dicas de uma tabela curada por preferência, grátis); caminho
  guiado por AWS Strands Agents SDK opcional com `MODEL_PROVIDER=ollama`
  (local) ou `MODEL_PROVIDER=bedrock` (ADR-013). Skill A2A
  `enrich_destination`. Só é chamado pelo Planner quando
  `AWS_AGENT_ENABLED=true`; falha ou desligamento nunca bloqueiam o
  fluxo (§11).
- **mcp-flight-search** (`mcp/flight-search`): servidor MCP (Streamable
  HTTP) com a tool `search_flights`, dados mock determinísticos (§23/§31).
- **mcp-hotel-search** (`mcp/hotel-search`): servidor MCP (Streamable
  HTTP) com a tool `search_hotels`, dados mock determinísticos (§23/§31).
- **mcp-places** (`mcp/places`): servidor MCP (Streamable HTTP) com a tool
  `search_places`, dados mock determinísticos, priorizados por
  `preferences` (§23/§31).
- **mcp-weather** (`mcp/weather`): servidor MCP (Streamable HTTP) com a
  tool `get_weather`, previsão mock local determinística (§5.4/§23).
- **mcp-currency** (`mcp/currency`): servidor MCP (Streamable HTTP) com a
  tool `convert_currency`, tabela de câmbio fixa e ilustrativa (§23/§31).
- **mcp-calculator** (`mcp/calculator`): servidor MCP (Streamable HTTP)
  com as tools `sum`/`subtract`/`multiply`/`divide` — cada uma uma
  operação binária fixa, sem `eval` (§33).
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

- Segurança JWT/OAuth (Fase 9) — hoje `AUTH_MODE=dev`, sem token real.
- Resiliência avançada (circuit breaker) — Fase 8. Timeout básico via
  `httpx`/`fetch` já existe nos clientes A2A/Registry/MCP; degradação
  por-dia do MCP Weather (CT-R03) já implementada no Activity Agent.
- AWS Full (`AgentCore Runtime → Strands → Bedrock`, §5.6) — fase futura,
  fora do escopo desta milestone (§38 "AgentCore — fase futura").

## AWS Enrichment (Fase 7)

O quinto especialista, `aws-enrichment-agent`, é opcional em dois
níveis: (1) se o Planner sequer tenta chamá-lo, controlado por
`AWS_AGENT_ENABLED` (lido pelo Planner); (2) se o próprio agente usa um
modelo real ou a tabela determinística, controlado por `MODEL_PROVIDER`
(lido pelo agente). Ver `docs/adr/ADR-013-enrichment-agent-strands-optional.md`
para os detalhes.

Ativar o profile `aws` (`make aws-local` / `make aws-lite`) não exige
nenhuma mudança no código do Planner (§37) — `aws-enrichment-agent` já
está registrado em `infrastructure/registry/agents.json` como qualquer
outro agente (`required: false`); o que muda por profile é apenas se o
container roda. Com o profile desligado, a tentativa de buscar seu Agent
Card falha rápido (conexão recusada) e é descartada silenciosamente pelo
`_agents_by_skill` do Planner, do mesmo jeito que qualquer outro agente
indisponível.

`docker-compose.yml` ganhou dois serviços atrás de `profiles: ["aws"]`:
`aws-enrichment-agent` e `ollama` (imagem oficial, com volume persistente
para os modelos baixados). Nenhum outro serviço depende deles — não há
`depends_on` apontando para um serviço com profile diferente do próprio,
o que quebraria `docker compose up` sem `--profile aws`.

## Paralelismo (Fase 6)

Flight, Hotel e Activity são independentes entre si — nenhum consome a
resposta do outro — então o Planner os delega concorrentemente via
`asyncio.gather` (`agents/planner-adk/app/agent.py`,
`handle_travel_request`), em vez de um após o outro. WAITING_SPECIALISTS
agora custa o tempo do especialista mais lento dos três, não a soma dos
três. A busca do Agent Card de cada agente descoberto (`_agents_by_skill`)
também foi paralelizada pelo mesmo motivo.

Budget continua fora desse fan-out, delegado depois — por design (§5.5),
já que ele precisa dos *resultados* de flight/hotel/activity, não do
`TravelRequest` bruto, então não pode começar antes deles terminarem.

Cada delegação individual (`_delegate_to_agent`) já trata sua própria
exceção e retorna `None` em vez de propagar — isso é o que torna seguro
rodar as três dentro de `asyncio.gather` sem `return_exceptions=True`: uma
falha em uma delegação nunca derruba as outras.

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
