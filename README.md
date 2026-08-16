# a2a-multi-agent-poc

**POC multiagente distribuída e poliglota**: seis agentes construídos em
frameworks e linguagens diferentes, interoperando exclusivamente por meio
de dois protocolos abertos — **A2A** (Agent2Agent, agente ↔ agente) e
**MCP** (Model Context Protocol, agente ↔ ferramenta) — sem nenhuma
biblioteca compartilhada de negócio entre eles. Caso de uso de referência:
um planejador de viagens que combina voo, hotel, roteiro de atividades e
orçamento em uma única resposta consolidada.

Especificação completa (requisitos, decisões e critérios de aceite):
[`a2a-multi-agent-poc-PROJECT_SPEC.md`](./a2a-multi-agent-poc-PROJECT_SPEC.md).

**Status:** as 9 fases do roteiro de implementação (§43 do spec) estão
completas — Foundation, Flight, Hotel, Activity, Budget, Paralelismo, AWS
Enrichment, Resiliência e Segurança. Detalhes fase a fase em
[`docs/architecture.md`](./docs/architecture.md).

---

## Sumário

- [Conceitos](#conceitos)
- [Por que esses protocolos](#por-que-esses-protocolos)
- [Arquitetura](#arquitetura)
- [Tecnologias por componente](#tecnologias-por-componente)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Como rodar](#como-rodar)
- [Autenticação](#autenticação)
- [Testando](#testando)
- [Observabilidade](#observabilidade)
- [Decisões de arquitetura (ADRs)](#decisões-de-arquitetura-adrs)
- [Limitações conhecidas e fora de escopo](#limitações-conhecidas-e-fora-de-escopo)

---

## Conceitos

Dois protocolos, duas responsabilidades, nunca misturadas:

| Protocolo | Liga | Pergunta que responde |
|---|---|---|
| **A2A** (Agent2Agent) | agente ↔ agente | "quem mais sabe resolver parte do meu problema, e como falo com ele sem conhecer sua implementação?" |
| **MCP** (Model Context Protocol) | agente ↔ ferramenta/dado/API | "como este agente busca ou calcula algo externo de forma padronizada?" |

Nenhum agente chama função interna de outro agente, nem importa código de
outro agente. Toda comunicação remota é HTTP + JSON-RPC 2.0 (A2A) ou MCP
sobre Streamable HTTP. O contrato é o protocolo, não a biblioteca — é por
isso que o Hotel Agent (TypeScript) interopera com os outros cinco
agentes (Python) sem que nenhum dos dois lados conheça a linguagem do
outro.

Outros conceitos-chave usados no projeto:

- **Agent Card**: documento JSON (`/.well-known/agent-card.json`) que
  cada agente expõe descrevendo suas *skills* (ex.: `search_flights`,
  `calculate_budget`). O Planner descobre e seleciona especialistas por
  *skill*, nunca por id fixo no código (§9 do spec) — trocar a
  implementação de um especialista, ou adicionar um novo, não exige
  mudar uma linha do Planner.
- **Agent Registry**: diretório simples (`infrastructure/registry`) que
  lista os agentes disponíveis e onde encontrar seus Agent Cards. Não
  substitui o Agent Card — é só o ponto de partida da descoberta.
- **Graceful degradation**: a resposta final do Planner nunca falha por
  inteiro só porque um especialista está fora do ar. Cada especialista
  tem seu próprio `status` (`SUCCESS`/`PARTIAL`/`UNAVAILABLE`/`UNKNOWN`);
  o `status` geral da viagem é `COMPLETED` sempre que os quatro
  especialistas centrais (flight/hotel/activity/budget) tiverem sucesso,
  independente do quinto (AWS Enrichment, opcional) estar ligado ou não.
- **Identidade de agente**: em `AUTH_MODE=jwt`, o token que um agente
  anexa a uma chamada A2A carrega quem ele é (`sub`), não só "alguém com
  a senha certa" — ver [Autenticação](#autenticação).

## Por que esses protocolos

- **A2A** existe porque orquestração multiagente clássica costuma
  acoplar o orquestrador à implementação de cada especialista (imports
  diretos, formatos de retorno ad hoc). Com A2A, o Planner só precisa
  saber falar JSON-RPC contra uma URL — o especialista pode ser reescrito
  do zero, trocar de linguagem ou de framework, e nada muda do lado do
  Planner além, no máximo, da URL no Registry.
- **MCP** existe pelo mesmo motivo, um nível abaixo: evita que cada
  agente reimplemente sua própria integração com a mesma fonte de dados
  (busca de voos, clima, câmbio). Um servidor MCP central expõe a
  ferramenta uma vez; qualquer agente, em qualquer linguagem, a consome
  da mesma forma.
- Juntos, os dois protocolos formam uma malha onde **camada de agente**
  (raciocínio, orquestração) e **camada de ferramenta** (busca, cálculo,
  dado externo) são explicitamente separadas — nenhum MCP Server toma
  decisão de negócio, nenhum agente reimplementa uma busca que já existe
  como MCP tool.

## Arquitetura

### Visão geral do fluxo

![Visão geral do fluxo: cliente → Planner → Agent Registry → especialistas via A2A → servidores MCP → observabilidade](./docs/img/Visao_Geral_Fluxo.png)

<details>
<summary>Fonte Mermaid deste diagrama</summary>

```mermaid
flowchart TB
    User(["Cliente HTTP"]) -->|"POST /v1/travel-requests"| Planner

    subgraph Orchestration["Orquestração"]
        Planner["Planner Agent<br/>Google ADK · Python · :8001"]
        Registry[("Agent Registry<br/>:8080")]
        Planner -->|"1 . descobre agentes"| Registry
    end

    subgraph Specialists["Especialistas (A2A, JSON-RPC 2.0)"]
        Flight["Flight Agent<br/>OpenAI Agents SDK · Python · :8002"]
        Hotel["Hotel Agent<br/>LangGraph · TypeScript · :8003"]
        Activity["Activity Agent<br/>BeeAI Framework · Python · :8004"]
        Budget["Budget Agent<br/>CrewAI · Python · :8005"]
        Enrichment["AWS Enrichment Agent (opcional)<br/>AWS Strands SDK · Python · :8006"]
    end

    Planner -->|"2 . fan-out paralelo"| Flight
    Planner -->|"2 . fan-out paralelo"| Hotel
    Planner -->|"2 . fan-out paralelo"| Activity
    Planner -->|"3 . depois dos 3 acima"| Budget
    Planner -.->|"4 . opcional, por último"| Enrichment

    subgraph Tools["Ferramentas (MCP, Streamable HTTP)"]
        MCPFlight[("mcp-flight-search<br/>:9001")]
        MCPHotel[("mcp-hotel-search<br/>:9002")]
        MCPPlaces[("mcp-places<br/>:9003")]
        MCPWeather[("mcp-weather<br/>:9004")]
        MCPCurrency[("mcp-currency<br/>:9005")]
        MCPCalc[("mcp-calculator<br/>:9006")]
    end

    Flight --> MCPFlight
    Hotel --> MCPHotel
    Activity --> MCPPlaces
    Activity --> MCPWeather
    Budget --> MCPCurrency
    Budget --> MCPCalc
    Enrichment -.-> MCPWeather
    Enrichment -.->|"opcional"| ModelProvider["Ollama (local) | Amazon Bedrock"]

    Planner -->|"5 . resposta consolidada"| User

    subgraph Observability["Observabilidade"]
        Otel["OTel Collector"]
        Jaeger["Jaeger UI<br/>:16686"]
        Otel --> Jaeger
    end

    Planner -.->|traces| Otel
    Flight -.-> Otel
    Hotel -.-> Otel
    Activity -.-> Otel
    Budget -.-> Otel
    Enrichment -.-> Otel
```

</details>

Flight, Hotel e Activity são independentes entre si e delegados em
paralelo (`asyncio.gather`); Budget só começa depois, porque precisa dos
**resultados** dos três, não do pedido bruto; o AWS Enrichment Agent é
opcional (`AWS_AGENT_ENABLED`) e sempre o último, nunca bloqueando o
`status: COMPLETED` — ver [`docs/architecture.md`](./docs/architecture.md#paralelismo-fase-6).

### Sequência de uma requisição

![Sequência de uma requisição: cliente chama o Planner, que descobre agentes no Registry, delega Flight/Hotel/Activity em paralelo e Budget depois, e retorna a resposta consolidada](./docs/img/Diagrama_Sequencia.png)

<details>
<summary>Fonte Mermaid deste diagrama</summary>

```mermaid
sequenceDiagram
    actor C as Cliente
    participant P as Planner
    participant R as Agent Registry
    participant F as Flight Agent
    participant H as Hotel Agent
    participant A as Activity Agent
    participant B as Budget Agent

    C->>P: POST /v1/travel-requests
    P->>R: GET agentes por skill
    R-->>P: Agent Cards (URLs)

    par fan-out paralelo
        P->>F: A2A message/send (Bearer token)
        F-->>P: FlightResult (status)
    and
        P->>H: A2A message/send (Bearer token)
        H-->>P: HotelResult (status)
    and
        P->>A: A2A message/send (Bearer token)
        A-->>P: ActivityResult (status)
    end

    P->>B: A2A message/send (flight+hotel+activity já resolvidos)
    B-->>P: BudgetResult (status)

    P-->>C: TravelResponse consolidado (status geral)
```

</details>

Se um especialista responder 401 (token ausente/inválido), 5xx, timeout
ou não responder, a chamada é tratada como falha desse especialista
específico — nunca derruba a requisição inteira (ver
[Resiliência](./docs/architecture.md#resiliência-fase-8) e
[Autenticação](#autenticação)).

## Tecnologias por componente

| Componente | Framework/SDK | Linguagem | Papel |
|---|---|---|---|
| **planner-agent** | Google ADK (scaffold) | Python 3.11 | Orquestrador — descobre, delega, consolida |
| **flight-agent** | OpenAI Agents SDK (opcional) | Python 3.11 | Busca e ranqueia voos |
| **hotel-agent** | LangGraph | TypeScript / Node 22 | Busca, filtra e ranqueia hotéis (grafo com estado) |
| **activity-agent** | BeeAI Framework (opcional) | Python 3.11 | Monta roteiro diário |
| **budget-agent** | CrewAI (opcional) | Python 3.11 | Consolida custos em orçamento |
| **aws-enrichment-agent** | AWS Strands Agents SDK (opcional) | Python 3.11 | Clima + dicas de destino (5º especialista, opcional) |
| **mock-specialist-agent** | — | Python 3.11 | Agente A2A trivial para validar o protocolo isoladamente |
| **mcp-flight-search / mcp-hotel-search / mcp-places / mcp-weather / mcp-currency / mcp-calculator** | `mcp` SDK oficial (FastMCP) | Python 3.11 | Servidores MCP (Streamable HTTP), dados mock determinísticos |
| **agent-registry** | FastAPI | Python 3.11 | Diretório de agentes |
| **otel-collector + jaeger** | OpenTelemetry Collector / Jaeger | — | Tracing distribuído (gRPC `:4317` e HTTP `:4318`) |

Cada agente Python roda em FastAPI + Uvicorn e expõe seu próprio adapter
A2A (`app/a2a/`, JSON-RPC 2.0 sobre `/a2a`); são seis cópias
deliberadamente independentes do mesmo contrato de wire, não uma
biblioteca compartilhada (ADR-008) — inclusive a reimplementação em
TypeScript do hotel-agent (ADR-010), prova real de interoperabilidade
entre linguagens. O caminho determinístico (grátis, sem LLM) é o padrão
em todo agente com framework "opcional" acima; o caminho guiado por LLM
só liga com a credencial correspondente configurada (ver ADRs
009/011/012/013).

## Estrutura do projeto

```text
a2a-multi-agent-poc/
├── a2a-multi-agent-poc-PROJECT_SPEC.md   # especificação completa (requisitos, fases, critérios de aceite)
├── docker-compose.yml                    # orquestra os 13+ serviços (perfil default + perfil "aws")
├── Makefile                              # atalhos: make local / aws-local / aws-lite / test / smoke
├── .env.example                          # todas as variáveis de ambiente, com defaults de dev seguros
│
├── agents/                               # os 6 agentes A2A
│   ├── planner-adk/                      #   orquestrador (Google ADK, Python)
│   │   ├── app/
│   │   │   ├── a2a/                      #     adapter A2A próprio (server.py, client.py, models.py)
│   │   │   ├── auth.py                   #     verify_request / mint_outgoing_token (Fase 9)
│   │   │   ├── resilience.py             #     circuit breaker por agente (Fase 8)
│   │   │   ├── agent.py                  #     orquestração: descoberta, delegação, consolidação
│   │   │   ├── config.py                 #     Settings (env vars)
│   │   │   ├── main.py                   #     FastAPI app + rotas
│   │   │   └── schemas.py                #     TravelRequest/TravelResponse (Pydantic)
│   │   ├── tests/                        #     suíte pytest do agente (59 testes)
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── flight-openai/                    #   especialista de voos (OpenAI Agents SDK opcional)
│   ├── hotel-langgraph/                  #   especialista de hotéis (LangGraph, TypeScript — src/ em vez de app/)
│   ├── activity-beeai/                   #   especialista de atividades (BeeAI Framework opcional)
│   ├── budget-crewai/                    #   especialista de orçamento (CrewAI opcional)
│   ├── aws-strands/                      #   especialista opcional de enriquecimento (AWS Strands SDK)
│   └── mock-specialist/                  #   agente A2A trivial para testar o protocolo isoladamente
│
├── mcp/                                  # os 6 servidores MCP (ferramentas)
│   ├── flight-search/  hotel-search/  places/  weather/  currency/  calculator/
│   └── <cada um>/app/server.py           #   FastMCP, tool(s) determinística(s), sem dependência externa real
│
├── infrastructure/
│   ├── registry/                         # Agent Registry (FastAPI + agents.json)
│   ├── observability/                    # config do OTel Collector
│   └── aws/                              # notas sobre o modo AWS opcional (Bedrock/AgentCore)
│
├── contracts/                            # contrato compartilhado entre Planner e especialistas
│   ├── schemas/                          #   JSON Schema de cada *Result e do TravelRequest/TravelResponse
│   └── examples/                         #   payloads de exemplo válidos contra os schemas
│
├── tests/                                # testes que cruzam múltiplos agentes
│   ├── contract/                         #   valida Agent Cards e schemas JSON
│   └── e2e/                              #   um arquivo por fase (test_fase2_flight.py ... test_fase7_enrichment.py)
│
├── scripts/
│   └── smoke-test.sh                     # sobe um request de ponta a ponta e confere o status
│
└── docs/
    ├── architecture.md                   # arquitetura fase a fase, com o "ainda não implementado"
    ├── local-development.md              # rodar cada agente fora do Docker, autenticação manual
    ├── testing.md                        # estratégia de teste completa, por nível
    ├── protocols.md / aws-mode.md
    └── adr/                              # 15 ADRs, uma decisão por arquivo (ver seção própria)
```

Cada agente e cada servidor MCP tem seu próprio `README.md` local com
detalhes específicos (endpoints, variáveis de ambiente, como rodar
isolado) — este README cobre a visão do sistema como um todo.

## Como rodar

Pré-requisitos: Docker + Docker Compose. Para rodar um agente fora do
Docker, também Python 3.11+ e/ou Node 22+ (ver
[`docs/local-development.md`](./docs/local-development.md)).

```bash
cp .env.example .env
make local
# equivalente a: docker compose up --build
```

Com o AWS Enrichment Agent ligado (5º especialista, opcional):

```bash
make aws-local   # AWS_AGENT_ENABLED=true MODEL_PROVIDER=ollama (100% local)
make aws-lite    # AWS_AGENT_ENABLED=true MODEL_PROVIDER=bedrock (requer credenciais AWS válidas, nunca commitadas)
```

Serviços expostos:

| Serviço | URL |
|---|---|
| Planner | http://localhost:8001 |
| Flight Agent | http://localhost:8002 |
| Hotel Agent | http://localhost:8003 |
| Activity Agent | http://localhost:8004 |
| Budget Agent | http://localhost:8005 |
| AWS Enrichment Agent (perfil `aws`) | http://localhost:8006 |
| Mock Specialist Agent | http://localhost:8099 |
| MCP Flight Search | http://localhost:9001 |
| MCP Hotel Search | http://localhost:9002 |
| MCP Places | http://localhost:9003 |
| MCP Weather | http://localhost:9004 |
| MCP Currency | http://localhost:9005 |
| MCP Calculator | http://localhost:9006 |
| Agent Registry | http://localhost:8080 |
| Ollama (perfil `aws`) | http://localhost:11434 |
| Jaeger UI | http://localhost:16686 |

Teste rápido de ponta a ponta:

```bash
./scripts/smoke-test.sh
```

Ou manualmente:

```bash
curl -X POST http://localhost:8001/v1/travel-requests \
  -H 'Content-Type: application/json' \
  -d @contracts/examples/travel-request.example.json
```

Com os quatro especialistas centrais respondendo `SUCCESS`, a resposta
traz `status: COMPLETED` — `flight`, `hotel`, `activities` e `budget`
todos `SUCCESS`, `budget.budget_status` classificado entre
`WITHIN_BUDGET`/`NEAR_LIMIT`/`OVER_BUDGET`. Com `AWS_AGENT_ENABLED=false`
(padrão), `enrichment` fica `SKIPPED`; com `AWS_AGENT_ENABLED=true`,
`enrichment` passa a `SUCCESS`/`UNAVAILABLE` de verdade — em nenhum dos
dois casos isso afeta `status: COMPLETED`.

> **Nota sobre `docker compose build`**: os `Dockerfile`s e o
> `docker-compose.yml` foram validados estruturalmente (`docker compose
> config`, grafo de `depends_on`, paths de `COPY`) mas o build de imagem
> real depende de acesso de rede a um registry de containers
> (`docker.io`/`ghcr.io`) — indisponível em alguns ambientes de CI/sandbox
> restritos. Rodando em uma máquina com acesso normal à internet,
> `make local` funciona sem passos extras.

## Autenticação

Toda chamada `POST /a2a` (recebida ou enviada) exige um bearer token —
`/health`, `/ready` e `/.well-known/agent-card.json` continuam abertos em
todos os agentes. Controlado por `AUTH_MODE`:

| Modo | Comportamento | Uso |
|---|---|---|
| `dev` (padrão) | token estático compartilhado (`DEV_AGENT_TOKEN`) | desenvolvimento local, `docker compose up` |
| `jwt` | JWT HS256 assinado com `JWT_SECRET`; claim `sub` = identidade de quem chama | prova de "agent identity" (§56) |
| `none` | sem verificação | debug isolado de um único agente; nunca é o default |

```bash
curl -s http://localhost:8002/a2a \
  -H "Authorization: Bearer local-development-only" \
  -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"..."}]}}}'
```

Detalhes completos (por que HS256 com segredo compartilhado em vez de um
IdP OAuth2/OIDC externo, por que só `/a2a` é protegido, como retry e
circuit breaker compõem com um 401) em
[ADR-015](./docs/adr/ADR-015-security-jwt-agent-identity-oidc-spike.md).

## Testando

Quatro níveis (§34 do spec) — unit por agente, contract (Agent Cards e
JSON Schemas), integration/e2e (um arquivo por fase, contra a stack
rodando) e um nível dedicado de resiliência/segurança. Total: 112 testes
unitários entre os 7 agentes (6 Python + hotel-agent TypeScript) mais os
testes de contrato e e2e na raiz.

```bash
cd agents/planner-adk && pip install -e . pytest && pytest -q
cd agents/hotel-langgraph && npm install && npm test
# ... mesmo padrão para os demais agentes — ver docs/local-development.md
```

Detalhes completos, incluindo o mapeamento dos cenários de resiliência
CT-R01..CT-R06 para os testes que os cobrem, em
[`docs/testing.md`](./docs/testing.md).

## Observabilidade

Todo agente instrumenta OpenTelemetry e exporta para o `otel-collector`
(agentes Python via gRPC `:4317`, hotel-agent via HTTP `:4318` — ambos os
protocolos suportados pelo mesmo collector), visualizável no Jaeger UI
(`http://localhost:16686`). Cada requisição carrega `trace_id` e
`correlation_id` propagados por toda a cadeia de chamadas A2A/MCP,
presentes também na resposta final do Planner (`metadata.trace_id`).

## Decisões de arquitetura (ADRs)

Cada decisão relevante tem seu próprio registro em
[`docs/adr/`](./docs/adr/), no formato Contexto → Decisão →
Consequências:

| ADR | Decisão |
|---|---|
| [001](./docs/adr/ADR-001-use-a2a-for-agent-communication.md) | Usar A2A para comunicação agente ↔ agente |
| [002](./docs/adr/ADR-002-use-mcp-for-tools.md) | Usar MCP para ferramentas |
| [003](./docs/adr/ADR-003-google-adk-as-planner.md) | Google ADK como scaffold do Planner |
| [004](./docs/adr/ADR-004-local-first.md) | Local-first via Docker Compose |
| [005](./docs/adr/ADR-005-aws-agent-optional.md) | AWS Agent opcional, fora do caminho crítico |
| [006](./docs/adr/ADR-006-opentelemetry.md) | OpenTelemetry como padrão de instrumentação |
| [007](./docs/adr/ADR-007-mock-mode.md) | Modo mock determinístico em todo MCP Server |
| [008](./docs/adr/ADR-008-custom-a2a-adapter.md) | Adapter A2A próprio, copiado por agente (não uma lib compartilhada) |
| [009](./docs/adr/ADR-009-flight-agent-llm-optional.md) | Caminho LLM opcional no Flight Agent |
| [010](./docs/adr/ADR-010-typescript-a2a-adapter-mirror.md) | Espelho do adapter A2A em TypeScript |
| [011](./docs/adr/ADR-011-activity-agent-beeai-optional.md) | Caminho BeeAI opcional no Activity Agent |
| [012](./docs/adr/ADR-012-budget-agent-crewai-optional.md) | Caminho CrewAI opcional no Budget Agent |
| [013](./docs/adr/ADR-013-enrichment-agent-strands-optional.md) | AWS Strands opcional; AgentCore como fase futura |
| [014](./docs/adr/ADR-014-resilience-retry-circuit-breaker.md) | Retry com backoff exponencial + circuit breaker por agente |
| [015](./docs/adr/ADR-015-security-jwt-agent-identity-oidc-spike.md) | Auth na rota `/a2a`, identidade via JWT, spike de OAuth/OIDC |

## Limitações conhecidas e fora de escopo

Itens deliberadamente fora do escopo desta POC (não são pendências —
estão documentados nos respectivos ADRs):

- Integração completa com um IdP OAuth2/OIDC externo real (client
  credentials, JWKS, chave assimétrica) — `AUTH_MODE=jwt` hoje é o
  "spike" pedido pelo §56, com HS256 e segredo compartilhado (ADR-015).
- AWS Full (`AgentCore Runtime → Strands → Bedrock`, §5.6) — fase futura
  fora do escopo desta milestone (ADR-013).
- Circuit breaker persistente/distribuído entre réplicas — hoje é em
  memória, por processo (ADR-014), coerente com esta POC não rodar
  múltiplas réplicas do Planner.
- Chaos test real contra containers Docker (derrubar/atrasar de
  propósito) — os cenários CT-R01..CT-R06 estão cobertos em
  unit/integration test do Planner, não como teste de infraestrutura.
- Pipeline de CI (lint → unit → contract → docker build → compose
  integration → e2e mock, §39) ainda não configurada.
