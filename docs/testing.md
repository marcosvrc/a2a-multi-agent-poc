# Estratégia de testes

Quatro níveis, conforme PROJECT_SPEC.md §34.

## Unit tests

Por agente, em `agents/<agente>/tests/` (Python, `pytest`) ou
`agents/hotel-langgraph/test/` (TypeScript, `node --test`). Cobrem
parsing, Agent Card, JSON-RPC (sucesso e erro), e no Planner as regras de
degradação e o roteamento de estados. No Hotel Agent, cobrem também cada
nó do grafo LangGraph isoladamente (`parse`, `filter`, `rank`) e o fluxo
completo (`graph.test.ts`), incluindo o caso de MCP indisponível.

## Contract tests

`tests/contract/`:

- `test_schemas.py` — offline, valida `contracts/examples/*.json` contra
  `contracts/schemas/*.json`.
- `test_agent_cards.py` — requer serviços rodando (`AGENT_URLS`), valida
  que cada Agent Card tem os campos obrigatórios do §8 (inclui o
  hotel-agent, provando que o Agent Card em TypeScript é indistinguível
  do Python do ponto de vista do protocolo).
- `test_flight_result_example_matches_schema` /
  `test_hotel_result_example_matches_schema` /
  `test_activity_result_example_matches_schema` /
  `test_budget_result_example_matches_schema` /
  `test_enrichment_result_example_matches_schema` — cada resultado por
  especialista tem seu próprio exemplo em `contracts/examples/` validado
  contra o schema correspondente.

## Integration / E2E

- `tests/e2e/test_m1_foundation.py` — requer `PLANNER_URL`, valida o
  critério de aceite da Milestone M1: descoberta via Registry + round-trip
  A2A completo + `TravelResponse` válido.
- `tests/e2e/test_fase2_flight.py` — requer `PLANNER_URL`, valida que o
  `flight-agent` real responde via A2A e que a `TravelResponse` final
  passa no JSON Schema completo, com `flight.status = SUCCESS` e
  `recommended_option_id` preenchido.
- `tests/e2e/test_fase3_hotel.py` — requer `PLANNER_URL`, valida que o
  `hotel-agent` (TypeScript) real responde via A2A e que a
  `TravelResponse` final passa no JSON Schema completo, com
  `flight.status = SUCCESS` e `hotel.status = SUCCESS` simultaneamente.
- `tests/e2e/test_fase4_activity.py` — requer `PLANNER_URL`, valida que o
  `activity-agent` (BeeAI) real responde via A2A e que a `TravelResponse`
  final tem `activities.status = SUCCESS` com um dia de roteiro por data
  da viagem, sem conflitos de horário, além de `flight`/`hotel`
  simultaneamente `SUCCESS`.
- `tests/e2e/test_fase5_budget.py` — requer `PLANNER_URL`, valida que o
  `budget-agent` (CrewAI) real responde via A2A recebendo os resultados
  de flight/hotel/activity (não o request bruto), e que com os quatro
  especialistas centrais `SUCCESS` a `TravelResponse` chega a
  `status = COMPLETED`. Também cobre o caso `OVER_BUDGET` com um limite
  de orçamento muito baixo.
- `tests/e2e/test_fase6_parallel.py` — requer `PLANNER_URL`, checagem de
  regressão de correção (não de timing — ver o docstring do arquivo para
  o porquê): confirma que delegar flight/hotel/activity concorrentemente
  ainda produz uma `TravelResponse` `COMPLETED` válida, e que um agente
  registrado sem nenhum skill relevante (`mock-specialist-agent`) não
  quebra o `asyncio.gather`. A prova real de que a delegação é
  concorrente (não apenas "ainda funciona") está no teste unitário
  `agents/planner-adk/tests/test_agent.py::test_flight_hotel_activity_are_delegated_in_parallel`,
  que controla latência de forma determinística.
- `tests/e2e/test_fase7_enrichment.py` — requer `PLANNER_URL`. Dividido em
  duas partes: um teste sempre executado (qualquer stack, com ou sem
  profile `aws`) que confirma que `enrichment.status` em
  `SKIPPED`/`SUCCESS`/`UNAVAILABLE` nunca impede `status = COMPLETED`; e
  dois testes adicionais, opt-in via `AWS_E2E_ENABLED=true` (só fazem
  sentido com a stack subida via `--profile aws` e
  `AWS_AGENT_ENABLED=true` no planner), que validam que o
  `aws-enrichment-agent` real responde via A2A com `enrichment.status =
  SUCCESS` e conteúdo (`weather_summary`/`destination_tips`).

## Resiliência

Fase 8 (§27/§35, ver `docs/adr/ADR-014-resilience-retry-circuit-breaker.md`):
retry com backoff exponencial (A2A e MCP) e circuit breaker por agente
(A2A). Os seis cenários CT-R01..CT-R06 do §35 estão todos cobertos por
teste unit/integration do Planner — não como chaos test real contra a
stack Docker (derrubar/atrasar containers de propósito), que permanece
um gap conhecido desta POC:

- **CT-R01** ("Flight indisponível → PARTIAL"):
  `agents/planner-adk/tests/test_agent.py::test_ct_r01_flight_unavailable_yields_partial`.
- **CT-R02** ("Hotel retorna timeout → retry; timeout; parcial"):
  `test_ct_r02_hotel_persistent_timeout_yields_partial` — o único CT-R0N
  que passa pelo `A2AClient` real (não um `send_text` mockado): faz o
  `httpx` subjacente lançar `TimeoutException` em toda tentativa contra
  o hotel-agent, e confirma tanto o número de tentativas (retry
  realmente aconteceu) quanto o resultado final (`PARTIAL`,
  `hotel.status = UNAVAILABLE`).
- **CT-R03** ("MCP Weather falha → Activity continua sem clima"): já
  coberto desde a Fase 4 em
  `agents/activity-beeai/tests/test_agent.py::test_weather_unavailable_still_returns_success`
  — inalterado por esta fase (retry no MCP client só atrasa a
  confirmação da falha via backoff, não muda o comportamento de
  degradação por-dia).
- **CT-R04** ("AWS Agent desligado → COMPLETED"):
  `test_ct_r04_aws_agent_disabled_yields_completed` (mesmo cenário de
  `test_enrichment_skipped_when_aws_agent_disabled`, Fase 7 — nomeado
  também com o rótulo CT-R0N para mapeamento 1:1 com o spec).
- **CT-R05** ("AWS Agent lança erro → COMPLETED,
  enrichment.status=UNAVAILABLE"):
  `test_ct_r05_aws_agent_raises_error_yields_completed_with_enrichment_unavailable`.
- **CT-R06** ("Budget falha → PARTIAL, budget.status=UNKNOWN"):
  `test_ct_r06_budget_failure_yields_partial_with_budget_status_unknown`.

Além dos CT-R0N, testes dedicados aos dois mecanismos em si:

- `agents/planner-adk/tests/test_resilience.py` — a máquina de estados
  do `CircuitBreaker` isolada (CLOSED → OPEN → HALF_OPEN → CLOSED/OPEN),
  sem depender do Planner.
- `agents/planner-adk/tests/test_a2a_client.py` — o retry do
  `A2AClient` isolado: sucesso sem retry, retry em timeout/5xx, sem
  retry em 4xx, sem retry em erro JSON-RPC (§27 "não repetir chamadas
  não idempotentes sem controle"), esgotamento de tentativas, backoff
  exponencial.
- `agents/planner-adk/tests/test_agent.py::test_circuit_breaker_opens_after_threshold_and_skips_further_delegation`
  e `test_circuit_breaker_is_per_agent_not_global` — a integração do
  circuit breaker com `_delegate_to_agent`.
- `agents/activity-beeai/tests/test_mcp_client.py` — o mesmo padrão de
  retry do lado MCP (`_with_retry`/`call_mcp_tool`), duplicado
  verbatim em `flight-openai`, `budget-crewai` e `aws-strands`.

## Segurança

Fase 9 (§7/§56, ver `docs/adr/ADR-015-security-jwt-agent-identity-oidc-spike.md`):
auth na rota `/a2a` de todo agente (6 Python + hotel-agent TypeScript).

- `agents/planner-adk/tests/test_auth.py` — 15 testes unitários de
  `verify_request`/`mint_outgoing_token` nos três modos (`dev`/`jwt`/
  `none`), incluindo JWT expirado, segredo errado, e round-trip
  mint→verify. Implementado uma vez em `planner-adk` como referência
  canônica — mesmo padrão já usado para `test_mcp_client.py` na Fase 8.
- `agents/planner-adk/tests/test_a2a_route_auth.py` — 5 testes de
  integração contra o FastAPI `app` real (não mockado): `AUTH_MODE`
  default é `"dev"`; `/a2a` rejeita token ausente/errado com 401; `/a2a`
  aceita o token correto; `/health`/`/ready`/agent-card continuam
  abertos sem qualquer header.
- `agents/planner-adk/tests/test_agent.py::test_delegation_attaches_bearer_auth_header` —
  confirma que `_delegate_to_agent` de fato anexa
  `Authorization: Bearer <token>` em toda chamada de saída.
- `agents/{mock-specialist,flight-openai,activity-beeai,budget-crewai,aws-strands}/tests/test_agent.py` —
  suítes existentes atualizadas para autenticar (`TestClient(app,
  headers={"Authorization": f"Bearer {settings.dev_agent_token}"})`),
  sem suíte de auth dedicada própria (mesma decisão de "implementar uma
  vez, propagar o wiring" já usada para o retry MCP na Fase 8).
- `agents/hotel-langgraph/test/auth.test.ts` — 11 testes cobrindo os
  três modos em TypeScript (`verifyRequest`/`mintOutgoingToken`), único
  agente sem um par Python para servir de referência.
- Contagem de testes por agente após esta fase: `planner-adk` 59,
  `mock-specialist` 8, `flight-openai` 5, `activity-beeai` 13,
  `budget-crewai` 17, `aws-strands` 9, `hotel-langgraph` 21 (10
  pré-existentes + 11 de auth).
- Não foi montada uma suíte live completa de `AUTH_MODE=jwt` contra a
  stack Docker de 13 serviços nesta fase — coberto no nível de
  unidade/integração (acima) mais o round-trip mint→verify; validação
  live do modo `jwt` fim-a-fim permanece um gap conhecido, coerente com
  a natureza desta POC (mesma ressalva já feita para chaos test real na
  Fase 8).

## CI

Pipeline mínima ainda não configurada nesta milestone (ver §39 do spec
para a ordem recomendada: lint → unit → contract → docker build → compose
integration → e2e mock).
