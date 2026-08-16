# ADR-014 — Resiliência: retry com backoff exponencial + circuit breaker por agente

## Status
Aceito

## Contexto
PROJECT_SPEC.md §27 exige `timeout`/`retry`/`exponential backoff`/`circuit
breaker`/`graceful degradation` em toda chamada de rede do sistema, com
defaults `timeout: 30s`, `retry: 2`, `backoff: exponential`, e a ressalva
explícita "não repetir chamadas não idempotentes sem controle". §35
formaliza seis cenários de teste (CT-R01..CT-R06) que o Planner já
degradava corretamente desde a Fase 5/6 (um specialist indisponível vira
`PARTIAL`, AWS desligado/erro nunca quebra `COMPLETED`), mas sem retry
real nem circuit breaker — cada requisição pagava o timeout completo
contra um agente já sabidamente fora do ar, e nenhuma chamada (A2A ou
MCP) era repetida em falha transitória.

## Decisão

### 1. Retry com backoff exponencial no cliente A2A (Planner -> especialista)
`agents/planner-adk/app/a2a/client.py::A2AClient._request_with_retry`
tenta de novo, com backoff exponencial (`backoff_base * 2**tentativa`),
apenas falhas de **transporte** sem evidência de que o especialista
recebeu/processou a requisição:

- `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.ReadError`,
  `httpx.RemoteProtocolError` — sempre retryable.
- `httpx.HTTPStatusError` com status `>= 500` — retryable (o servidor
  remoto sinalizou uma falha própria, provavelmente transitória).
- `httpx.HTTPStatusError` com status `< 500` — **nunca** retryable: o
  outro lado rejeitou a requisição deliberadamente, repetir não muda
  nada.
- Erro em nível de JSON-RPC (`error` no corpo de uma resposta HTTP 200,
  vira `A2AClientError`) — **nunca** retryable: o especialista *recebeu
  e processou* a requisição, só respondeu com um erro de aplicação.
  Repetir esse caso violaria a ressalva do §27 sobre chamadas não
  idempotentes.

`retry_attempts`/`retry_backoff_base_seconds` vêm de `Settings`
(`AGENT_MAX_RETRIES`, já existia como campo escrito mas nunca lido antes
desta fase; `AGENT_RETRY_BACKOFF_BASE_SECONDS`, novo).

### 2. Circuit breaker por agente (`app/resilience.py`)
`CircuitBreaker`/`CircuitBreakerRegistry` implementam a máquina de
estados clássica (CLOSED -> OPEN após N falhas consecutivas -> HALF_OPEN
após um cooldown -> CLOSED em sucesso / OPEN de novo em falha),
configurável via `CIRCUIT_BREAKER_FAILURE_THRESHOLD` (padrão 3) e
`CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS` (padrão 30). Um registry global
em `app/agent.py` mantém um breaker por `agent_id`, compartilhado entre
`_fetch_agent_card` (fase DISCOVERING_AGENTS) e `_delegate_to_agent`
(fase DELEGATING) — as duas são chamadas ao mesmo agente remoto e um
agente comprovadamente fora do ar não deveria ser re-tentado em nenhuma
das duas.

Isso é estritamente adicional ao retry: o retry lida com uma falha
transitória *dentro* de uma única requisição; o circuit breaker lida com
um agente que já demonstrou estar fora do ar *através de várias
requisições consecutivas* — sem ele, cada nova `POST
/v1/travel-requests` pagaria o timeout completo (+ os retries) contra um
agente já conhecidamente indisponível, em vez de falhar rápido.

### 3. `budget.status = UNKNOWN` em vez de `UNAVAILABLE` (CT-R06)
`_parse_specialist_result` ganhou um parâmetro `unavailable_status`
(padrão `"UNAVAILABLE"`, usado por flight/hotel/activity/enrichment).
`_delegate_budget` passa `unavailable_status="UNKNOWN"` — únicos dois
motivos: (1) é literalmente o texto do CT-R06 no spec
("`budget.status=UNKNOWN`"); (2) `BudgetResult.status` já tinha
`UNKNOWN` como valor default antes mesmo desta fase (usado quando nenhum
agente advertise `calculate_budget`), então esta mudança só torna
consistente os dois casos de "budget não deu certo" que já existiam
separadamente.

### 4. Retry também no lado Agent -> MCP
O mesmo padrão de retry-com-backoff foi replicado (não generalizado numa
lib compartilhada — mesma decisão de "cópia deliberada por agente" já
tomada em ADR-008/ADR-010 para o adapter A2A) em `call_mcp_tool`
(`agents/{activity-beeai,budget-crewai,aws-strands}/app/mcp_client.py`),
em `search_flights` (`agents/flight-openai/app/mcp_client.py`) e em
`searchHotels` (`agents/hotel-langgraph/src/mcpClient.ts`, versão
TypeScript). Todas as tools MCP chamadas nesta POC (`search_flights`,
`search_hotels`, `search_places`, `get_weather`,
`sum`/`subtract`/`multiply`, `convert_currency`) são leituras ou
computações puras — seguras para repetir sem a ressalva de
não-idempotência que se aplica ao lado A2A.

## Consequências
- `AGENT_MAX_RETRIES` (já existia, nunca lido) passa a controlar de
  verdade o número de retries do cliente A2A.
- Testes novos: `agents/planner-adk/tests/test_resilience.py` (unit da
  máquina de estados do circuit breaker, isolada), `test_a2a_client.py`
  (retry do A2AClient — sucesso/timeout/5xx/4xx/erro JSON-RPC/backoff
  exponencial), seis testes `test_ct_r0N_*` mapeando 1:1 para CT-R01..
  CT-R06 do §35, e dois testes de circuit breaker (abre após threshold e
  volta a fechar em sucesso; isolamento por agente). No lado MCP, novo
  `agents/activity-beeai/tests/test_mcp_client.py` cobre o mesmo padrão
  (`_with_retry`/`call_mcp_tool`), representativo dos quatro agentes
  Python que compartilham essa função.
- `tests/planner-adk/tests/conftest.py` ganhou uma fixture `autouse` que
  reseta `app.agent.circuit_breakers` antes de cada teste — sem isso, um
  teste que abre o breaker de `"flight-agent"` deliberadamente deixaria
  esse breaker OPEN para qualquer teste seguinte que reuse o mesmo
  agent-id, um bug clássico de estado global compartilhado entre testes.
- CT-R03 ("MCP Weather falha -> Activity continua sem clima") já estava
  coberto desde a Fase 4 (`test_weather_unavailable_still_returns_success`)
  e não muda: retry no MCP client faz a falha demorar um pouco mais para
  se confirmar (backoff), mas o comportamento de degradação por-dia
  continua o mesmo depois de esgotado.
- O circuit breaker do Planner é **em memória, por processo** — reinicia
  toda vez que o container do Planner reinicia, e não é compartilhado
  entre réplicas (fora de escopo: esta POC não roda múltiplas réplicas
  do Planner). Um circuit breaker persistente/distribuído é explicitamente
  fora de escopo desta milestone.
- Não foi montada a suíte formal com derrubada/atraso proposital de
  containers via Docker (§35 menciona isso como o mecanismo ideal de
  teste) — os CT-R0x aqui são testados no nível de unidade/integração do
  Planner (mockando o cliente A2A/httpx), não como chaos test real contra
  a stack Docker. Chaos testing real contra containers permanece um
  gap conhecido, coerente com a natureza desta POC.
