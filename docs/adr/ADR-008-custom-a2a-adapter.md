# ADR-008 — Adapter A2A próprio em vez do `a2a-sdk` oficial (Python) nesta milestone

## Status
Aceito, revisitar na Fase 2+

## Contexto
`a2a-sdk` (PyPI, v1.1.2) existe e foi avaliado, mas sua API pública nesta
versão é baseada em modelos protobuf (`a2a_pb2.AgentCard`, etc.) e em
`RequestHandler`/`AgentExecutor` cuja assinatura exata não pôde ser
verificada com confiança dentro do escopo desta milestone (sem acesso
confirmado à documentação oficial atualizada). PROJECT_SPEC.md §42 regra 8
proíbe inventar métodos/classes de SDK.

## Decisão
Implementar um adapter HTTP próprio e minimalista (`app/a2a/`) que segue os
conceitos do protocolo A2A descritos em PROJECT_SPEC.md §6.1 e
§8 (Agent Card, Message/Parts, Task/TaskStatus, JSON-RPC 2.0 com
`message/send`, `tasks/get`, `tasks/cancel`), conforme expressamente
permitido pela regra 7 do §42: "Se um SDK não fornecer A2A nativamente,
implemente um adapter compatível."

## Consequências
- O adapter cobre o subconjunto necessário para M1: descoberta via Agent
  Card, envio de mensagem síncrono, consulta de tarefa. Streaming
  (`message/stream`, SSE) não está implementado (permitido por §6.5).
- Antes da Fase 2 (Flight Agent com OpenAI Agents SDK), revisar a
  documentação oficial de `a2a-sdk` e `a2a-protocol.org` para decidir se
  migramos para o SDK oficial ou mantemos o adapter — decisão a ser
  registrada em um novo ADR quando isso acontecer, sem alterar o contrato
  externo (`/.well-known/agent-card.json`, `/a2a` JSON-RPC) já validado
  pelos testes de contrato/E2E desta milestone.
