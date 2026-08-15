# ADR-005 — Agente AWS é opcional e nunca crítico

## Status
Aceito (agente ainda não implementado nesta milestone)

## Contexto
PROJECT_SPEC.md §5.6 exige que o AWS Enrichment Agent nunca bloqueie o
Planner nem faça parte do caminho crítico.

## Decisão
`AWS_AGENT_ENABLED=false` é o padrão. Quando `true`, o Planner apenas
tenta enriquecer a resposta; qualquer falha ou ausência do agente resulta
em `enrichment.status=SKIPPED` ou `UNAVAILABLE`, nunca em falha do fluxo
principal (regra já implementada em `agents/planner-adk/app/agent.py`,
mesmo antes do agente AWS existir).

## Consequências
- A implementação do agente Strands em si fica para a Fase 7.
