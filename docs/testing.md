# Estratégia de testes

Quatro níveis, conforme PROJECT_SPEC.md §34.

## Unit tests

Por agente, em `agents/<agente>/tests/`. Cobrem parsing, Agent Card,
JSON-RPC (sucesso e erro), e no Planner as regras de degradação e o
roteamento de estados.

## Contract tests

`tests/contract/`:

- `test_schemas.py` — offline, valida `contracts/examples/*.json` contra
  `contracts/schemas/*.json`.
- `test_agent_cards.py` — requer serviços rodando (`AGENT_URLS`), valida
  que cada Agent Card tem os campos obrigatórios do §8.

## Integration / E2E

- `tests/e2e/test_m1_foundation.py` — requer `PLANNER_URL`, valida o
  critério de aceite da Milestone M1: descoberta via Registry + round-trip
  A2A completo + `TravelResponse` válido.
- `tests/e2e/test_fase2_flight.py` — requer `PLANNER_URL`, valida que o
  `flight-agent` real responde via A2A e que a `TravelResponse` final
  passa no JSON Schema completo, com `flight.status = SUCCESS` e
  `recommended_option_id` preenchido.

## Resiliência

Ainda não implementado (Fase 8). Os testes CT-R01..CT-R06 do §35 serão
adicionados quando houver especialistas reais para derrubar/atrasar.

## CI

Pipeline mínima ainda não configurada nesta milestone (ver §39 do spec
para a ordem recomendada: lint → unit → contract → docker build → compose
integration → e2e mock).
