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
- `test_hotel_result_example_matches_schema` / `test_flight_result_...` /
  `test_activity_result_example_matches_schema` — cada resultado por
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

## Resiliência

A suíte formal (CT-R01..CT-R06 do §35, com derrubada/atraso proposital de
serviços) ainda não foi montada (Fase 8). Um caso já está coberto como
efeito colateral da implementação do Activity Agent: CT-R03 ("MCP Weather
falha → Activity continua sem clima") é testado em
`agents/activity-beeai/tests/test_agent.py::test_weather_unavailable_still_returns_success`.

## CI

Pipeline mínima ainda não configurada nesta milestone (ver §39 do spec
para a ordem recomendada: lint → unit → contract → docker build → compose
integration → e2e mock).
