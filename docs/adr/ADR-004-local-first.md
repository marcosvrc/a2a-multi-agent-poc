# ADR-004 — Local-first

## Status
Aceito

## Contexto
A POC deve funcionar totalmente offline/local, sem depender de
credenciais de nuvem (PROJECT_SPEC.md §1, item 4, e RNF-03).

## Decisão
`docker-compose up --build` sobe toda a stack obrigatória (Planner, Mock
Agent nesta milestone, Registry, OTel Collector, Jaeger) sem exigir
nenhuma variável de ambiente de nuvem. `MOCK_MODE=true` é o padrão em
`.env.example`.

## Consequências
- O agente AWS (`aws-enrichment-agent`) fica atrás de um profile Docker
  opcional (`--profile aws`), introduzido na Fase 7.
