# A2A Multi-Agent POC — Especificação de Arquitetura, Requisitos e Implementação

> Documento de referência para implementação por desenvolvedores ou LLMs de coding.
>
> **Objetivo principal:** construir uma POC multiagente distribuída com 6 agentes implementados em tecnologias diferentes, interoperando por **A2A (Agent2Agent)** e consumindo ferramentas por **MCP (Model Context Protocol)**. O ambiente deve rodar prioritariamente de forma local via Docker Compose, com componentes AWS opcionais para evitar custo desnecessário.

---

## 1. Visão geral

O projeto deverá demonstrar que agentes construídos com frameworks, linguagens e provedores diferentes conseguem interoperar sem conhecer a implementação interna uns dos outros.

A POC deverá comprovar os seguintes princípios:

1. **Agent-to-Agent via A2A**
   - Toda comunicação entre agentes remotos deverá utilizar A2A.
   - Nenhum agente deverá chamar diretamente funções internas de outro agente.
   - O contrato entre agentes deverá ser independente do framework utilizado.

2. **Agent-to-Tool via MCP**
   - Ferramentas, integrações, APIs externas e fontes de dados reutilizáveis deverão ser expostas preferencialmente como servidores MCP.
   - Os agentes não devem duplicar integrações externas quando um MCP Server puder centralizá-las.

3. **Interoperabilidade**
   - Cada agente deverá utilizar um framework diferente.
   - O sistema deverá utilizar ao menos Python e TypeScript.
   - O protocolo deverá ser o elemento de integração, não bibliotecas compartilhadas entre frameworks.

4. **Local-first**
   - O sistema deverá funcionar localmente via Docker Compose.
   - Serviços AWS deverão ser opcionais.
   - A POC principal deverá continuar funcional sem credenciais AWS.

5. **Cloud-optional**
   - O agente AWS poderá usar Strands localmente.
   - Amazon Bedrock e Amazon Bedrock AgentCore poderão ser ativados opcionalmente.
   - O agente AWS não poderá estar no caminho crítico da aplicação.

6. **Observabilidade**
   - Todas as chamadas importantes deverão possuir `trace_id`, `correlation_id` e logs estruturados.
   - OpenTelemetry deverá ser o padrão de instrumentação.
   - Jaeger deverá ser utilizado localmente para visualização de traces.

7. **Resiliência**
   - Falha de um agente especialista deverá ser tratada.
   - Falha do agente AWS opcional nunca deverá impedir a conclusão do fluxo principal.
   - Timeouts, retries e circuit breaker deverão ser considerados.

---

# 2. Nome sugerido do projeto

Nome padrão:

```text
a2a-multi-agent-poc
```

Alternativas aceitáveis:

```text
agent-mesh-lab
polyglot-agent-mesh
multi-agent-protocol-lab
agent-interoperability-poc
```

Para este documento será utilizado:

```text
a2a-multi-agent-poc
```

---

# 3. Caso de uso da POC

A aplicação simulará um **planejador de viagens multiagente**.

Exemplo de solicitação:

```text
Planeje uma viagem para Florianópolis de 20 a 24 de setembro para duas pessoas,
saindo de São Paulo, com orçamento máximo de R$ 8.000.
Quero praia, gastronomia e atividades ao ar livre.
```

Resultado esperado:

```json
{
  "request_id": "uuid",
  "destination": "Florianopolis",
  "travelers": 2,
  "period": {
    "start": "2026-09-20",
    "end": "2026-09-24"
  },
  "flight": {},
  "hotel": {},
  "activities": [],
  "budget": {},
  "enrichment": {},
  "status": "completed"
}
```

O domínio de viagem é apenas um mecanismo didático para demonstrar:

- descoberta;
- delegação;
- paralelismo;
- dependências;
- tool calling;
- comunicação distribuída;
- streaming;
- observabilidade;
- falhas;
- fallback;
- uso opcional de cloud.

---

# 4. Agentes

O sistema terá seis agentes.

| ID | Agente | Framework | Linguagem | Obrigatório | Responsabilidade |
|---|---|---|---|---|---|
| AG-01 | Planner Agent | Google ADK | Python | Sim | Orquestração global |
| AG-02 | Flight Agent | OpenAI Agents SDK | Python | Sim | Pesquisa e comparação de voos |
| AG-03 | Hotel Agent | LangGraph | TypeScript | Sim | Pesquisa e ranking de hotéis |
| AG-04 | Activity Agent | BeeAI Framework | Python | Sim | Criação do roteiro de atividades |
| AG-05 | Budget Agent | CrewAI | Python | Sim | Consolidação e otimização de custos |
| AG-06 | AWS Enrichment Agent | AWS Strands Agents | Python | Não | Clima e enriquecimento opcional |

---

# 5. Responsabilidades por agente

## 5.1 AG-01 — Planner Agent

### Tecnologia

```text
Google ADK
Python
```

### Responsabilidades

- receber a solicitação do usuário;
- validar os campos mínimos;
- gerar `request_id`;
- iniciar o trace distribuído;
- descobrir os agentes disponíveis;
- consultar Agent Cards;
- selecionar especialistas;
- chamar Flight, Hotel e Activity em paralelo;
- consolidar resultados parciais;
- chamar Budget após os especialistas;
- opcionalmente chamar AWS Enrichment;
- tratar falhas;
- montar a resposta final;
- nunca executar lógica específica de voo, hotel, atividade ou clima.

### Não deve

- acessar diretamente API de voos;
- acessar diretamente API de hotéis;
- acessar diretamente API meteorológica;
- calcular orçamento completo;
- depender do agente AWS.

---

## 5.2 AG-02 — Flight Agent

### Tecnologia

```text
OpenAI Agents SDK
Python
```

### Responsabilidades

- interpretar requisitos relacionados a voo;
- consultar ferramenta MCP de pesquisa de voos;
- normalizar resultados;
- ordenar opções;
- retornar no máximo 5 alternativas;
- indicar opção recomendada;
- informar ausência de dados reais quando a ferramenta estiver em modo mock.

### Skill A2A principal

```text
search_flights
```

### Ferramentas

```text
MCP Flight Search
```

---

## 5.3 AG-03 — Hotel Agent

### Tecnologia

```text
LangGraph
TypeScript
```

### Responsabilidades

Implementar explicitamente um fluxo com estado:

```text
parse_request
      ↓
search_hotels
      ↓
filter_results
      ↓
rank_results
      ↓
build_response
```

Critérios mínimos:

- destino;
- datas;
- quantidade de hóspedes;
- orçamento;
- localização;
- preferências.

### Skill A2A

```text
search_hotels
```

### Ferramenta

```text
MCP Hotel Search
```

---

## 5.4 AG-04 — Activity Agent

### Tecnologia

```text
BeeAI Framework
Python
```

> Usar Python para A2A nesta POC.

### Responsabilidades

- criar roteiro diário;
- respeitar duração da viagem;
- evitar conflito de horários;
- considerar preferências;
- usar clima quando disponível;
- permitir execução sem informação meteorológica.

### Skills

```text
plan_activities
optimize_itinerary
```

### Ferramentas

```text
MCP Places
MCP Weather
```

O Weather MCP poderá usar mock local.

---

## 5.5 AG-05 — Budget Agent

### Tecnologia

```text
CrewAI
Python
```

### Responsabilidades

Receber:

- voo;
- hotel;
- atividades;
- orçamento máximo.

Calcular:

```text
flight_cost
hotel_cost
activity_cost
food_estimate
transport_estimate
total
remaining_budget
budget_status
```

### Status possíveis

```text
WITHIN_BUDGET
NEAR_LIMIT
OVER_BUDGET
UNKNOWN
```

### Skill

```text
calculate_budget
```

### Skill opcional

```text
optimize_budget
```

### Ferramentas

```text
MCP Currency
MCP Calculator
```

---

## 5.6 AG-06 — AWS Enrichment Agent

### Tecnologia

```text
AWS Strands Agents SDK
Python
```

### Obrigatoriedade

```text
OPTIONAL
```

O sistema deverá funcionar sem este agente.

### Responsabilidade reduzida

O agente AWS será responsável apenas por enriquecimento:

```text
weather enrichment
destination tips
short recommendations
```

Não poderá:

- aprovar ou rejeitar uma viagem;
- calcular orçamento final;
- escolher hotel;
- escolher voo;
- bloquear o Planner;
- armazenar estado essencial.

### Skill

```text
enrich_destination
```

### Provider

Configuração:

```text
AWS_AGENT_ENABLED=false
MODEL_PROVIDER=ollama
```

ou:

```text
AWS_AGENT_ENABLED=true
MODEL_PROVIDER=ollama
```

ou:

```text
AWS_AGENT_ENABLED=true
MODEL_PROVIDER=bedrock
```

### Modos

#### Local

```text
Strands
  ↓
Ollama
```

#### AWS Lite

```text
Strands
  ↓
Amazon Bedrock
```

#### AWS Full

```text
A2A
 ↓
Amazon Bedrock AgentCore Runtime
 ↓
Strands
 ↓
Amazon Bedrock
```

---

# 6. Protocolos obrigatórios

## 6.1 A2A

Uso:

```text
Agent → Agent
```

A2A deverá ser o contrato padrão de comunicação remota entre os agentes.

Requisitos:

- Agent Card;
- Messages;
- Parts;
- Tasks quando aplicável;
- Task Status;
- Artifacts;
- streaming quando disponível;
- `contextId`;
- `taskId`;
- cancelamento quando suportado;
- tratamento de erro padronizado.

### Endpoint de descoberta

Cada agente deverá fornecer:

```text
/.well-known/agent-card.json
```

Caso o SDK utilizado exponha outro endpoint padrão, criar compatibilidade ou um adapter HTTP.

---

## 6.2 MCP

Uso:

```text
Agent → Tool
Agent → API
Agent → Data
```

Versão alvo:

```text
MCP 2026-07-28
```

Quando uma biblioteca ainda não suportar integralmente essa versão, permitir negociação/fallback para a versão suportada.

Servidores MCP mínimos:

```text
mcp-weather
mcp-flight-search
mcp-hotel-search
mcp-places
mcp-currency
mcp-calculator
```

Os servidores deverão rodar localmente.

---

## 6.3 HTTP

Todos os serviços deverão expor HTTP para:

```text
health
ready
metrics
A2A
MCP quando Streamable HTTP for usado
```

---

## 6.4 JSON-RPC

Quando aplicável ao binding A2A escolhido, utilizar JSON-RPC 2.0.

Operações que deverão ser suportadas quando compatíveis com o SDK:

```text
message/send
message/stream
tasks/get
tasks/cancel
```

---

## 6.5 SSE

Utilizar Server-Sent Events para streaming A2A quando suportado.

O sistema deverá funcionar também sem streaming.

---

# 7. Segurança

Para a POC local:

```text
AUTH_MODE=dev
```

Implementar ao menos:

- API Key entre serviços ou token estático em desenvolvimento;
- headers de correlação;
- secrets somente via environment variables;
- nenhum secret versionado.

Preparar arquitetura para:

```text
OAuth 2.1
OIDC
JWT
```

Headers sugeridos:

```text
Authorization: Bearer <token>
X-Request-Id: <uuid>
X-Correlation-Id: <uuid>
traceparent: ...
```

---

# 8. Agent Card

Todos os agentes deverão possuir Agent Card.

Estrutura conceitual:

```json
{
  "name": "flight-agent",
  "description": "Searches and ranks flight options",
  "version": "0.1.0",
  "capabilities": {
    "streaming": true
  },
  "skills": [
    {
      "id": "search_flights",
      "name": "Search Flights",
      "description": "Searches for flights based on origin, destination and dates"
    }
  ]
}
```

Cada Agent Card deverá ser validado em teste automatizado.

---

# 9. Agent Registry

Criar um componente próprio para fins didáticos:

```text
agent-registry
```

Ele não substituirá o Agent Card.

Responsabilidade:

- listar agentes conhecidos;
- expor URL;
- health status;
- tags;
- Agent Card URL.

### Endpoint

```text
GET /agents
GET /agents/{agent_id}
GET /agents/{agent_id}/health
```

Exemplo:

```json
[
  {
    "id": "flight-agent",
    "url": "http://flight-agent:8002",
    "agent_card_url": "http://flight-agent:8002/.well-known/agent-card.json",
    "required": true
  }
]
```

O Planner deverá usar Registry + Agent Card.

Não fazer hard-code de capabilities no Planner.

---

# 10. Fluxo principal

## 10.1 Entrada

```text
User
  ↓
Planner
```

## 10.2 Fan-out

Executar preferencialmente em paralelo:

```text
Planner
  ├─A2A→ Flight
  ├─A2A→ Hotel
  └─A2A→ Activity
```

## 10.3 Consolidação

```text
Flight ─┐
Hotel ──┼→ Planner
Activity┘
```

## 10.4 Budget

```text
Planner
  ↓ A2A
Budget
```

## 10.5 Enrichment opcional

```text
Planner
  ↓
AWS agent available?
  ├─ no → continue
  └─ yes
       ↓ A2A
     AWS Enrichment
```

## 10.6 Resposta

```text
Planner
  ↓
User
```

---

# 11. Regras de degradação

## Flight indisponível

A resposta poderá ser:

```text
PARTIAL
```

desde que o Planner informe que voo não foi obtido.

## Hotel indisponível

Pode retornar parcial.

## Activity indisponível

Pode retornar parcial.

## Budget indisponível

O Planner deverá responder:

```text
budget_status=UNKNOWN
```

## AWS Enrichment indisponível

Ignorar.

Não marcar o fluxo como falha.

---

# 12. Estados da execução

Estados sugeridos:

```text
RECEIVED
DISCOVERING_AGENTS
DELEGATING
WAITING_SPECIALISTS
CALCULATING_BUDGET
OPTIONAL_ENRICHMENT
CONSOLIDATING
COMPLETED
PARTIAL
FAILED
```

O Planner deverá registrar mudanças de estado nos logs.

---

# 13. Contratos compartilhados

Criar pasta:

```text
contracts/
```

Não compartilhar lógica de framework.

Compartilhar somente:

- JSON Schema;
- OpenAPI quando necessário;
- exemplos de payload;
- documentação;
- schemas A2A auxiliares.

### TravelRequest

```json
{
  "request_id": "uuid",
  "origin": "Sao Paulo",
  "destination": "Florianopolis",
  "start_date": "2026-09-20",
  "end_date": "2026-09-24",
  "travelers": 2,
  "budget": 8000,
  "currency": "BRL",
  "preferences": [
    "beach",
    "gastronomy",
    "outdoor"
  ]
}
```

---

# 14. Resposta final

```json
{
  "request_id": "uuid",
  "status": "COMPLETED",
  "flight": {
    "status": "SUCCESS",
    "options": []
  },
  "hotel": {
    "status": "SUCCESS",
    "options": []
  },
  "activities": {
    "status": "SUCCESS",
    "days": []
  },
  "budget": {
    "status": "WITHIN_BUDGET",
    "total": 7450,
    "limit": 8000,
    "remaining": 550
  },
  "enrichment": {
    "status": "SKIPPED",
    "provider": null
  },
  "metadata": {
    "trace_id": "...",
    "duration_ms": 0
  }
}
```

---

# 15. Estrutura do monorepo

```text
a2a-multi-agent-poc/
│
├── README.md
├── Makefile
├── docker-compose.yml
├── docker-compose.aws.yml
├── .env.example
├── .gitignore
│
├── docs/
│   ├── architecture.md
│   ├── protocols.md
│   ├── local-development.md
│   ├── aws-mode.md
│   ├── testing.md
│   └── adr/
│
├── contracts/
│   ├── schemas/
│   │   ├── travel-request.schema.json
│   │   ├── travel-response.schema.json
│   │   ├── flight-result.schema.json
│   │   ├── hotel-result.schema.json
│   │   ├── activity-result.schema.json
│   │   ├── budget-result.schema.json
│   │   └── enrichment-result.schema.json
│   │
│   └── examples/
│
├── agents/
│   ├── planner-adk/
│   ├── flight-openai/
│   ├── hotel-langgraph/
│   ├── activity-beeai/
│   ├── budget-crewai/
│   └── enrichment-strands/
│
├── mcp/
│   ├── weather/
│   ├── flight-search/
│   ├── hotel-search/
│   ├── places/
│   ├── currency/
│   └── calculator/
│
├── infrastructure/
│   ├── registry/
│   ├── gateway/
│   ├── observability/
│   │   ├── otel-collector.yaml
│   │   └── jaeger/
│   └── aws/
│
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── e2e/
│   └── resilience/
│
└── scripts/
    ├── healthcheck.sh
    ├── smoke-test.sh
    └── seed-mocks.sh
```

---

# 16. Estrutura mínima de cada agente Python

```text
agent/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── agent.py
│   ├── config.py
│   ├── schemas.py
│   ├── telemetry.py
│   └── a2a/
│       ├── server.py
│       ├── client.py
│       └── agent_card.py
├── tests/
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

# 17. Estrutura do Hotel Agent TypeScript

```text
hotel-langgraph/
├── src/
│   ├── index.ts
│   ├── graph.ts
│   ├── config.ts
│   ├── schemas.ts
│   ├── telemetry.ts
│   ├── nodes/
│   │   ├── parse.ts
│   │   ├── search.ts
│   │   ├── filter.ts
│   │   └── rank.ts
│   └── a2a/
├── test/
├── Dockerfile
├── package.json
├── tsconfig.json
└── README.md
```

---

# 18. Docker Compose

A execução local deverá usar Docker Compose.

## Serviços obrigatórios

```text
planner-agent
flight-agent
hotel-agent
activity-agent
budget-agent

agent-registry

mcp-flight
mcp-hotel
mcp-places
mcp-weather
mcp-currency
mcp-calculator

otel-collector
jaeger
```

## Serviço opcional

```text
aws-enrichment-agent
```

---

# 19. Docker Compose — baseline

Usar este arquivo como ponto de partida, ajustando comandos e imagens conforme a implementação real.

```yaml
services:

  planner-agent:
    build:
      context: ./agents/planner-adk
    environment:
      SERVICE_NAME: planner-agent
      PORT: 8001
      AGENT_REGISTRY_URL: http://agent-registry:8080
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
      AWS_AGENT_ENABLED: ${AWS_AGENT_ENABLED:-false}
    ports:
      - "8001:8001"
    depends_on:
      agent-registry:
        condition: service_healthy
      otel-collector:
        condition: service_started
    networks:
      - agent-net

  flight-agent:
    build:
      context: ./agents/flight-openai
    environment:
      SERVICE_NAME: flight-agent
      PORT: 8002
      MCP_FLIGHT_URL: http://mcp-flight:9001
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
    ports:
      - "8002:8002"
    networks:
      - agent-net

  hotel-agent:
    build:
      context: ./agents/hotel-langgraph
    environment:
      SERVICE_NAME: hotel-agent
      PORT: 8003
      MCP_HOTEL_URL: http://mcp-hotel:9002
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    ports:
      - "8003:8003"
    networks:
      - agent-net

  activity-agent:
    build:
      context: ./agents/activity-beeai
    environment:
      SERVICE_NAME: activity-agent
      PORT: 8004
      MCP_PLACES_URL: http://mcp-places:9003
      MCP_WEATHER_URL: http://mcp-weather:9004
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    ports:
      - "8004:8004"
    networks:
      - agent-net

  budget-agent:
    build:
      context: ./agents/budget-crewai
    environment:
      SERVICE_NAME: budget-agent
      PORT: 8005
      MCP_CURRENCY_URL: http://mcp-currency:9005
      MCP_CALCULATOR_URL: http://mcp-calculator:9006
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    ports:
      - "8005:8005"
    networks:
      - agent-net

  aws-enrichment-agent:
    profiles:
      - aws
    build:
      context: ./agents/enrichment-strands
    environment:
      SERVICE_NAME: aws-enrichment-agent
      PORT: 8006
      MODEL_PROVIDER: ${MODEL_PROVIDER:-ollama}
      AWS_REGION: ${AWS_REGION:-us-east-1}
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    ports:
      - "8006:8006"
    networks:
      - agent-net

  agent-registry:
    build:
      context: ./infrastructure/registry
    environment:
      PORT: 8080
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 5s
      timeout: 3s
      retries: 20
    networks:
      - agent-net

  mcp-flight:
    build:
      context: ./mcp/flight-search
    environment:
      PORT: 9001
      MOCK_MODE: ${MOCK_MODE:-true}
    networks:
      - agent-net

  mcp-hotel:
    build:
      context: ./mcp/hotel-search
    environment:
      PORT: 9002
      MOCK_MODE: ${MOCK_MODE:-true}
    networks:
      - agent-net

  mcp-places:
    build:
      context: ./mcp/places
    environment:
      PORT: 9003
      MOCK_MODE: ${MOCK_MODE:-true}
    networks:
      - agent-net

  mcp-weather:
    build:
      context: ./mcp/weather
    environment:
      PORT: 9004
      MOCK_MODE: ${MOCK_MODE:-true}
    networks:
      - agent-net

  mcp-currency:
    build:
      context: ./mcp/currency
    environment:
      PORT: 9005
      MOCK_MODE: ${MOCK_MODE:-true}
    networks:
      - agent-net

  mcp-calculator:
    build:
      context: ./mcp/calculator
    environment:
      PORT: 9006
    networks:
      - agent-net

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command:
      - --config=/etc/otelcol/config.yaml
    volumes:
      - ./infrastructure/observability/otel-collector.yaml:/etc/otelcol/config.yaml:ro
    ports:
      - "4317:4317"
      - "4318:4318"
    networks:
      - agent-net

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
    networks:
      - agent-net

networks:
  agent-net:
    driver: bridge
```

Observação:

```text
Não fixar tag `latest` na versão final do projeto.
```

Após a primeira execução estável, fixar versões de todas as imagens.

---

# 20. Profiles do Docker Compose

## Local sem AWS

```bash
docker compose up --build
```

## Com agente AWS local

```bash
AWS_AGENT_ENABLED=true \
MODEL_PROVIDER=ollama \
docker compose --profile aws up --build
```

## Com Bedrock

```bash
AWS_AGENT_ENABLED=true \
MODEL_PROVIDER=bedrock \
docker compose --profile aws up --build
```

---

# 21. Makefile

Criar comandos:

```makefile
.PHONY: local aws-local aws-lite down test smoke logs

local:
	docker compose up --build

aws-local:
	AWS_AGENT_ENABLED=true MODEL_PROVIDER=ollama docker compose --profile aws up --build

aws-lite:
	AWS_AGENT_ENABLED=true MODEL_PROVIDER=bedrock docker compose --profile aws up --build

down:
	docker compose --profile aws down

test:
	pytest -q

smoke:
	./scripts/smoke-test.sh

logs:
	docker compose logs -f
```

Ajustar testes para múltiplas linguagens.

---

# 22. Configuração

Criar:

```text
.env.example
```

Conteúdo mínimo:

```dotenv
ENVIRONMENT=local
LOG_LEVEL=INFO
MOCK_MODE=true

OPENAI_API_KEY=

AWS_AGENT_ENABLED=false
MODEL_PROVIDER=ollama
AWS_REGION=us-east-1

AGENT_REQUEST_TIMEOUT_SECONDS=30
AGENT_MAX_RETRIES=2

OTEL_SERVICE_NAMESPACE=a2a-poc
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

AUTH_MODE=dev
DEV_AGENT_TOKEN=local-development-only
```

Nunca incluir credenciais reais.

---

# 23. Mock Mode

A POC deverá rodar mesmo sem APIs comerciais.

Configuração:

```text
MOCK_MODE=true
```

Os servidores MCP deverão retornar dados determinísticos.

Exemplo de voo mock:

```json
{
  "provider": "mock",
  "flights": [
    {
      "id": "FL-001",
      "origin": "GRU",
      "destination": "FLN",
      "price": 850,
      "currency": "BRL"
    }
  ]
}
```

Isso é essencial para:

- CI;
- desenvolvimento local;
- demos;
- testes de contrato;
- evitar custo.

---

# 24. Observabilidade

## OpenTelemetry obrigatório

Instrumentar:

```text
Planner request
A2A calls
MCP calls
LLM calls
workflow nodes
retries
errors
```

### Spans esperados

```text
planner.request
  ├── registry.discovery
  ├── a2a.flight
  │    └── mcp.flight_search
  ├── a2a.hotel
  │    └── mcp.hotel_search
  ├── a2a.activity
  │    ├── mcp.places
  │    └── mcp.weather
  ├── a2a.budget
  │    ├── mcp.currency
  │    └── mcp.calculator
  └── a2a.aws_enrichment
```

---

# 25. Logs

Usar JSON estruturado.

Exemplo:

```json
{
  "timestamp": "2026-08-15T18:00:00Z",
  "level": "INFO",
  "service": "planner-agent",
  "event": "agent_call_started",
  "target_agent": "flight-agent",
  "request_id": "uuid",
  "correlation_id": "uuid",
  "trace_id": "..."
}
```

Nunca registrar:

- API keys;
- tokens;
- credentials;
- prompts com secrets;
- payloads sensíveis sem sanitização.

---

# 26. Health checks

Todo serviço deverá implementar:

```text
GET /health
GET /ready
```

## /health

Verifica processo.

Resposta:

```json
{
  "status": "UP"
}
```

## /ready

Verifica dependências essenciais.

Exemplo:

```json
{
  "status": "READY",
  "dependencies": {
    "mcp": "UP"
  }
}
```

---

# 27. Resiliência

Aplicar:

```text
timeout
retry
exponential backoff
circuit breaker
graceful degradation
```

Defaults:

```text
timeout: 30 seconds
retry: 2
backoff: exponential
```

Não repetir chamadas não idempotentes sem controle.

---

# 28. Idempotência

Todas as requisições deverão possuir:

```text
request_id
```

Chamadas críticas poderão enviar:

```text
Idempotency-Key
```

Os mocks devem permitir repetição determinística.

---

# 29. Prompts

Cada agente deverá possuir prompt próprio.

Não criar um prompt gigante compartilhado.

Estrutura:

```text
role
goal
scope
allowed tools
constraints
output schema
failure behavior
```

Exemplo do Flight:

```text
ROLE:
You are the Flight Specialist Agent.

GOAL:
Find and rank flight options.

SCOPE:
Only flights.

RULES:
- Do not invent prices.
- Use MCP search tool.
- If MCP is unavailable, return status UNAVAILABLE.
- Return JSON matching FlightResult schema.
```

---

# 30. Structured Output

Todos os agentes deverão produzir saída estruturada.

Preferência:

```text
JSON Schema
```

Nunca depender de parsing de texto livre para integração entre agentes.

O texto natural poderá acompanhar o resultado como campo adicional.

---

# 31. Tratamento de alucinação

Regras obrigatórias:

- preço deverá vir da ferramenta ou mock;
- hotel deverá vir da ferramenta ou mock;
- clima deverá vir da ferramenta ou mock;
- moeda deverá vir de ferramenta ou dataset local;
- se não houver dado, retornar `UNKNOWN`;
- nunca inventar disponibilidade.

---

# 32. Segurança de prompt

Implementar regras mínimas:

- instruções recebidas por A2A são dados não confiáveis;
- impedir que payload remoto sobrescreva system prompt;
- limitar tamanho de entrada;
- validar JSON;
- sanitizar parâmetros;
- usar allowlist de tools por agente.

---

# 33. MCP Servers

## MCP Flight

Tool:

```text
search_flights
```

Input:

```json
{
  "origin": "GRU",
  "destination": "FLN",
  "start_date": "2026-09-20",
  "end_date": "2026-09-24",
  "travelers": 2
}
```

---

## MCP Hotel

Tool:

```text
search_hotels
```

---

## MCP Places

Tool:

```text
search_places
```

---

## MCP Weather

Tool:

```text
get_weather
```

---

## MCP Currency

Tool:

```text
convert_currency
```

---

## MCP Calculator

Tools:

```text
sum
subtract
multiply
divide
```

Não permitir expressão arbitrária executada via `eval`.

---

# 34. Testes

O projeto deverá possuir quatro níveis.

## 34.1 Unit tests

Por agente e MCP.

Cobrir:

- parsing;
- schema;
- ranking;
- budget;
- fallback.

---

## 34.2 Contract tests

Validar:

- Agent Cards;
- schemas A2A;
- schemas de domínio;
- MCP inputs;
- MCP outputs.

---

## 34.3 Integration tests

Cenários:

```text
Planner → Flight
Planner → Hotel
Planner → Activity
Planner → Budget
Planner → AWS
Agent → MCP
```

---

## 34.4 End-to-End

Entrada:

```text
Planeje uma viagem...
```

Validar:

- status;
- schema;
- trace;
- resultado consolidado.

---

# 35. Testes de resiliência

Criar testes específicos:

### CT-R01

Flight indisponível.

Esperado:

```text
PARTIAL
```

### CT-R02

Hotel retorna timeout.

Esperado:

- retry;
- timeout;
- parcial.

### CT-R03

MCP Weather falha.

Esperado:

Activity continua sem clima.

### CT-R04

AWS Agent desligado.

Esperado:

```text
COMPLETED
```

### CT-R05

AWS Agent lança erro.

Esperado:

```text
COMPLETED
enrichment.status=UNAVAILABLE
```

### CT-R06

Budget falha.

Esperado:

```text
PARTIAL
budget.status=UNKNOWN
```

---

# 36. Smoke test

Criar:

```text
scripts/smoke-test.sh
```

O script deverá:

1. verificar Registry;
2. verificar Agent Cards;
3. verificar health;
4. enviar solicitação;
5. validar HTTP status;
6. validar `request_id`;
7. validar resposta JSON;
8. imprimir URL do Jaeger.

---

# 37. Critérios de aceite

A primeira versão estará concluída quando:

- [ ] os cinco agentes obrigatórios executarem via Docker Compose;
- [ ] cada agente utilizar framework diferente;
- [ ] ao menos um agente estiver em TypeScript;
- [ ] todos expuserem Agent Card;
- [ ] Planner descobrir agentes dinamicamente;
- [ ] comunicação agente-agente utilizar A2A;
- [ ] comunicação agente-tool utilizar MCP;
- [ ] Flight usar MCP;
- [ ] Hotel usar MCP;
- [ ] Activity usar MCP;
- [ ] Budget usar MCP;
- [ ] execução funcionar com `MOCK_MODE=true`;
- [ ] agente AWS puder ficar desligado;
- [ ] ativar o profile AWS não exigir alteração no código do Planner;
- [ ] OpenTelemetry gerar traces;
- [ ] Jaeger exibir o fluxo completo;
- [ ] logs contiverem `request_id`;
- [ ] testes de contrato passarem;
- [ ] teste E2E passar;
- [ ] cenário de AWS desligada retornar sucesso;
- [ ] README explicar execução.

---

# 38. Critérios de aceite AWS

## Local Strands

- [ ] Strands roda em container;
- [ ] usa provider local;
- [ ] expõe A2A;
- [ ] Planner consegue chamá-lo;
- [ ] pode ser removido sem quebrar sistema.

## Bedrock

- [ ] provider pode ser alterado por environment variable;
- [ ] credenciais não ficam no repositório;
- [ ] região configurável;
- [ ] falha de Bedrock não quebra fluxo principal.

## AgentCore — fase futura

- [ ] agente pode ser empacotado para AgentCore Runtime;
- [ ] mantém Agent Card;
- [ ] mantém contrato A2A;
- [ ] Planner local consegue consumir endpoint remoto autenticado.

---

# 39. CI

Pipeline mínima:

```text
lint
  ↓
unit tests
  ↓
contract tests
  ↓
docker build
  ↓
docker compose integration
  ↓
e2e mock
```

Não executar Bedrock por padrão na CI.

Criar job separado manual:

```text
aws-integration
```

---

# 40. Versionamento

Fixar versões.

Evitar:

```text
latest
*
>= sem limite superior em componentes críticos
```

Criar arquivos lock:

Python:

```text
uv.lock
```

ou equivalente.

TypeScript:

```text
package-lock.json
```

ou:

```text
pnpm-lock.yaml
```

---

# 41. ADRs

Criar Architecture Decision Records.

Mínimos:

```text
ADR-001-use-a2a-for-agent-communication.md
ADR-002-use-mcp-for-tools.md
ADR-003-google-adk-as-planner.md
ADR-004-local-first.md
ADR-005-aws-agent-optional.md
ADR-006-opentelemetry.md
ADR-007-mock-mode.md
```

---

# 42. Desenvolvimento orientado a LLM

Ao solicitar implementação para uma LLM, usar as seguintes regras:

```text
1. Não implemente todos os agentes simultaneamente.
2. Preserve os contratos definidos em /contracts.
3. Não crie acoplamento direto entre frameworks.
4. Toda comunicação remota Agent-Agent deve usar A2A.
5. Toda integração externa reutilizável deve preferir MCP.
6. Não substitua A2A por chamadas REST proprietárias silenciosamente.
7. Se um SDK não fornecer A2A nativamente, implemente um adapter compatível.
8. Não invente métodos ou classes de SDK.
9. Consulte documentação oficial antes de adicionar dependências.
10. Fixe versões após confirmar compatibilidade.
11. Sempre inclua testes.
12. Não coloque secrets no código.
13. AWS deve permanecer opcional.
14. MOCK_MODE deve funcionar sem APIs externas.
15. Structured output deve ser validado por schema.
```

---

# 43. Ordem recomendada de implementação

## Fase 0 — Bootstrap

Criar:

```text
repo
docker compose
contracts
registry
otel
jaeger
```

---

## Fase 1 — Planner + Mock Agent

Antes dos frameworks especialistas, criar um agente A2A mock.

Objetivo:

```text
validar A2A end-to-end
```

---

## Fase 2 — Flight

Implementar:

```text
OpenAI Agents SDK
+
A2A adapter/server
+
MCP Flight
```

---

## Fase 3 — Hotel

Implementar:

```text
LangGraph TypeScript
+
A2A
+
MCP Hotel
```

---

## Fase 4 — Activity

Implementar:

```text
BeeAI
+
A2A
+
MCP Places
+
MCP Weather
```

---

## Fase 5 — Budget

Implementar:

```text
CrewAI
+
A2A
+
MCP Currency
+
MCP Calculator
```

---

## Fase 6 — Paralelismo

Alterar Planner:

```text
Flight ┐
Hotel  ├ parallel
Activity┘
```

---

## Fase 7 — AWS

Adicionar:

```text
Strands
```

Primeiro local.

Depois:

```text
Bedrock
```

Depois, opcionalmente:

```text
AgentCore
```

---

## Fase 8 — Resiliência

Adicionar:

```text
timeouts
retries
circuit breaker
graceful degradation
```

---

## Fase 9 — Security

Adicionar:

```text
JWT
OAuth/OIDC
agent identity
```

---

# 44. Definição de Done por agente

Um agente só é considerado pronto quando:

- [ ] inicia via Docker;
- [ ] possui `/health`;
- [ ] possui `/ready`;
- [ ] possui Agent Card;
- [ ] recebe chamada A2A;
- [ ] valida input;
- [ ] executa sua função;
- [ ] chama MCP quando aplicável;
- [ ] valida output;
- [ ] propaga trace;
- [ ] gera logs estruturados;
- [ ] possui unit tests;
- [ ] possui contract tests;
- [ ] possui README;
- [ ] não contém secrets.

---

# 45. Requisitos não funcionais

## RNF-01 — Portabilidade

Sistema deve executar em:

```text
macOS
Linux
Docker Desktop
Rancher Desktop
```

Windows é desejável, não obrigatório para a primeira versão.

---

## RNF-02 — Startup

Ambiente mock deverá iniciar com:

```bash
docker compose up --build
```

---

## RNF-03 — Custo

Modo padrão não deverá exigir:

```text
AWS
OpenAI
Google Cloud
serviço SaaS pago
```

Quando um framework exigir um LLM, permitir provider local ou mock sempre que tecnicamente possível.

---

## RNF-04 — Latência

Não definir SLA de produção.

Meta para mock local:

```text
p95 < 10 s
```

A meta serve apenas para detectar regressões graves.

---

## RNF-05 — Escalabilidade

Não é objetivo da POC implementar Kubernetes.

Arquitetura deve permitir futura migração:

```text
Docker Compose
     ↓
Kubernetes / ECS / AgentCore
```

---

## RNF-06 — Manutenibilidade

Cada agente deverá ser deployável independentemente.

---

## RNF-07 — Observabilidade

100% das chamadas A2A devem propagar correlação.

---

# 46. Itens fora do escopo inicial

Não implementar na primeira versão:

```text
Kubernetes
service mesh
banco vetorial
RAG complexo
memória de longo prazo
pagamentos
reserva real
compra de passagem
compra de hotel
interface mobile
produção multi-region
HA
auto scaling
fine-tuning
```

Esses itens poderão ser adicionados futuramente.

---

# 47. Possível evolução

Depois da POC:

```text
API Gateway
     ↓
Planner
     ↓
Agent Registry
     ↓
Agent Mesh
     ↓
MCP Gateway
```

Possíveis plataformas:

```text
AWS ECS
Amazon EKS
Amazon Bedrock AgentCore
Kubernetes
```

---

# 48. Diagrama conceitual

```text
                               USER
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Planner Agent │
                         │  Google ADK   │
                         │    Python     │
                         └───────┬───────┘
                                 │
                                A2A
                                 │
            ┌────────────────────┼─────────────────────┐
            │                    │                     │
            ▼                    ▼                     ▼
     ┌──────────────┐     ┌──────────────┐      ┌──────────────┐
     │ Flight Agent │     │ Hotel Agent  │      │Activity Agent│
     │ OpenAI SDK   │     │ LangGraph    │      │ BeeAI        │
     │ Python       │     │ TypeScript   │      │ Python       │
     └──────┬───────┘     └──────┬───────┘      └──────┬───────┘
            │ MCP                │ MCP                 │ MCP
            ▼                    ▼                     ▼
       Flight Search         Hotel Search        Places / Weather
            │                    │                     │
            └────────────────────┼─────────────────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Budget Agent  │
                         │ CrewAI        │
                         │ Python        │
                         └───────┬───────┘
                                 │
                                 │ optional A2A
                                 ▼
                         ┌────────────────┐
                         │ AWS Enrichment │
                         │ Strands        │
                         │ Python         │
                         └───────┬────────┘
                                 │
                           optional cloud
                                 │
                         ┌───────┴────────┐
                         │                │
                      Ollama          Bedrock
                                          │
                                     AgentCore
                                     (future)
```

---

# 49. Protocolo x responsabilidade

Regra arquitetural definitiva:

```text
A2A = Agent ↔ Agent

MCP = Agent ↔ Tool / API / Data

HTTP = transporte

JSON-RPC = binding/RPC quando aplicável

SSE = streaming

OAuth/OIDC/JWT = identidade e autorização

OpenTelemetry = observabilidade

Docker = runtime local
```

---

# 50. Checklist para iniciar o projeto

## Repositório

- [ ] criar monorepo;
- [ ] adicionar `.gitignore`;
- [ ] criar `.env.example`;
- [ ] criar README;
- [ ] criar Makefile;
- [ ] criar docker-compose.

## Contratos

- [ ] TravelRequest;
- [ ] TravelResponse;
- [ ] FlightResult;
- [ ] HotelResult;
- [ ] ActivityResult;
- [ ] BudgetResult;
- [ ] EnrichmentResult.

## Infra

- [ ] Registry;
- [ ] OpenTelemetry Collector;
- [ ] Jaeger;
- [ ] rede Docker.

## Planner

- [ ] Google ADK;
- [ ] A2A client;
- [ ] Agent discovery;
- [ ] fan-out;
- [ ] aggregation.

## Flight

- [ ] OpenAI Agents SDK;
- [ ] A2A server;
- [ ] Flight MCP.

## Hotel

- [ ] LangGraph;
- [ ] TypeScript;
- [ ] A2A endpoint;
- [ ] Hotel MCP.

## Activity

- [ ] BeeAI;
- [ ] A2A;
- [ ] Places MCP;
- [ ] Weather MCP.

## Budget

- [ ] CrewAI;
- [ ] A2A;
- [ ] Currency MCP;
- [ ] Calculator MCP.

## AWS

- [ ] Strands;
- [ ] profile `aws`;
- [ ] provider Ollama;
- [ ] provider Bedrock;
- [ ] AgentCore somente posteriormente.

## QA

- [ ] unit;
- [ ] contract;
- [ ] integration;
- [ ] resilience;
- [ ] E2E;
- [ ] smoke.

---

# 51. Primeira milestone

## Milestone: `M1 - A2A Local Foundation`

Objetivo:

```text
Planner Google ADK
      │
      │ A2A
      ▼
Mock Specialist Agent
```

Entregáveis:

- docker-compose;
- Registry;
- Planner;
- um Mock A2A Agent;
- Agent Cards;
- OpenTelemetry;
- Jaeger;
- teste E2E.

Essa milestone deverá ser concluída antes da implementação dos cinco especialistas.

---

# 52. Segunda milestone

## `M2 - Multi-Framework Agents`

Entregáveis:

```text
Flight / OpenAI
Hotel / LangGraph
Activity / BeeAI
Budget / CrewAI
```

Todos interoperando por A2A.

---

# 53. Terceira milestone

## `M3 - MCP Tool Mesh`

Entregáveis:

```text
6 MCP Servers
mock mode
contract tests
```

---

# 54. Quarta milestone

## `M4 - AWS Optional Agent`

Entregáveis:

```text
Strands
Docker profile
Ollama
Bedrock optional
```

---

# 55. Quinta milestone

## `M5 - Resilience + Observability`

Entregáveis:

```text
retry
timeout
circuit breaker
partial responses
distributed traces
structured logs
```

---

# 56. Sexta milestone

## `M6 - Security`

Entregáveis:

```text
JWT
agent identity
OAuth/OIDC spike
secret management
```

---

# 57. Prompt inicial recomendado para coding LLM

Use este prompt junto deste documento:

```text
Você está implementando o projeto a2a-multi-agent-poc.

Leia integralmente o arquivo PROJECT_SPEC.md antes de escrever código.

Regras obrigatórias:

1. Trate PROJECT_SPEC.md como fonte de verdade arquitetural.
2. Não implemente componentes fora da milestone solicitada.
3. Comunicação entre agentes remotos deve utilizar A2A.
4. Comunicação com ferramentas reutilizáveis deve utilizar MCP.
5. Não crie integração proprietária direta entre frameworks.
6. Não altere schemas compartilhados sem explicar a incompatibilidade.
7. Use documentação oficial dos SDKs antes de escrever integração.
8. Não invente APIs de frameworks.
9. Sempre crie testes.
10. Não adicione secrets.
11. AWS deve permanecer opcional.
12. MOCK_MODE deve funcionar sem APIs pagas.
13. Outputs de integração devem ser estruturados e validados.
14. Preserve trace_id, request_id e correlation_id.
15. Pare ao concluir a milestone solicitada e reporte:
   - arquivos criados;
   - decisões;
   - testes executados;
   - limitações;
   - próximo passo recomendado.
```

---

# 58. Fontes oficiais de referência

As versões e APIs dos frameworks devem ser verificadas antes da implementação. Não confiar apenas neste documento para nomes exatos de classes, pois SDKs agentic evoluem rapidamente.

## A2A

```text
https://a2a-protocol.org/latest/
https://a2a-protocol.org/latest/topics/key-concepts/
```

## MCP

```text
https://modelcontextprotocol.io/specification/
https://blog.modelcontextprotocol.io/posts/2026-07-28/
```

## Google ADK

```text
https://google.github.io/adk-docs/a2a/
https://google.github.io/adk-docs/a2a/quickstart-exposing/
https://google.github.io/adk-docs/a2a/quickstart-consuming/
```

## OpenAI Agents SDK

```text
https://openai.github.io/openai-agents-python/
https://openai.github.io/openai-agents-python/mcp/
```

## LangGraph / Agent Server

```text
https://docs.langchain.com/langsmith/server-a2a
https://docs.langchain.com/langsmith/server-mcp
```

## BeeAI

```text
https://framework.beeai.dev/introduction/welcome
https://framework.beeai.dev/integrations/a2a
https://framework.beeai.dev/integrations/mcp
```

## CrewAI

```text
https://docs.crewai.com/en/learn/a2a-agent-delegation
https://docs.crewai.com/en/mcp/overview
```

## AWS Strands

```text
https://strandsagents.com/docs/user-guide/quickstart/overview/
https://strandsagents.com/docs/user-guide/concepts/multi-agent/agent-to-agent/
```

## Amazon Bedrock AgentCore

```text
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html
```

---

# 59. Observações de compatibilidade verificadas em agosto de 2026

Antes de começar a implementação, considerar:

- A2A é um padrão aberto para descoberta, delegação e troca de resultados entre agentes.
- MCP deve ser tratado como protocolo de tool/data integration.
- A especificação MCP 2026-07-28 tornou o core stateless e trouxe mudanças relevantes de autorização, extensões e SDKs.
- Google ADK possui suporte A2A para exposição e consumo de agentes, mas determinados recursos podem permanecer marcados como experimentais em versões específicas.
- LangSmith Agent Server expõe endpoint A2A e também MCP.
- CrewAI documenta A2A como primitive de delegação e possui integração MCP.
- BeeAI oferece integração A2A e MCP; o suporte A2A documentado deve ser usado em Python na POC.
- Strands possui suporte a A2A, MCP e padrões multiagentes.
- Amazon Bedrock AgentCore Runtime pode hospedar servidores A2A e MCP.
- O AgentCore deve ser tratado como evolução opcional e não como requisito da execução local.

---

# 60. Resultado esperado da POC

Ao final, o projeto deverá conseguir demonstrar, visualmente no Jaeger, um fluxo como:

```text
USER
 ↓
Google ADK Planner
 ├──A2A──> OpenAI Flight
 │           └──MCP──> Flight Search
 │
 ├──A2A──> LangGraph Hotel
 │           └──MCP──> Hotel Search
 │
 ├──A2A──> BeeAI Activity
 │           ├──MCP──> Places
 │           └──MCP──> Weather
 │
 ├──A2A──> CrewAI Budget
 │           ├──MCP──> Currency
 │           └──MCP──> Calculator
 │
 └──A2A──> Strands Enrichment
             └── optional
                 ├── Ollama
                 └── Amazon Bedrock
```

O objetivo da POC não é provar qual framework é melhor.

O objetivo é provar:

```text
Framework ≠ Integration Contract
```

e:

```text
A2A fornece interoperabilidade Agent-to-Agent
MCP fornece interoperabilidade Agent-to-Tool
```

Esse princípio deverá permanecer como a principal decisão arquitetural do projeto.
