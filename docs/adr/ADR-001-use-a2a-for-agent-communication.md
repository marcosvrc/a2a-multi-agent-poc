# ADR-001 — Usar A2A para comunicação Agent-to-Agent

## Status
Aceito

## Contexto
O objetivo da POC é provar que agentes construídos em frameworks e
linguagens diferentes conseguem interoperar sem conhecer a implementação
interna uns dos outros (PROJECT_SPEC.md §1).

## Decisão
Toda comunicação remota entre agentes usa o protocolo A2A: Agent Card em
`/.well-known/agent-card.json`, mensagens/partes, tarefas com estado, e
JSON-RPC 2.0 (`message/send`, `tasks/get`, `tasks/cancel`) sobre HTTP.
Nenhum agente chama funções internas de outro agente.

## Consequências
- Cada agente precisa expor um endpoint A2A compatível, mesmo quando o SDK
  do framework não fornece isso nativamente (ver ADR-008).
- Streaming (SSE) é opcional; o sistema funciona sem ele (§6.5).
