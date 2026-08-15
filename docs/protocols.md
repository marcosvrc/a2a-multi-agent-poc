# Protocolos

## A2A (implementado nesta milestone via adapter próprio)

Ver ADR-008 para a justificativa de não usar o `a2a-sdk` oficial ainda.

- Agent Card: `GET /.well-known/agent-card.json`
- JSON-RPC 2.0: `POST /a2a`
  - `message/send` — envia uma `Message` (role `user`, `parts` de texto ou
    dados), retorna uma `Task` completa (síncrono nesta milestone).
  - `tasks/get` — consulta uma `Task` por `id`.
  - `tasks/cancel` — melhor esforço; a maioria das tasks já completa antes
    de poder ser cancelada nesta milestone.
- `message/stream` (SSE) — **não implementado**. Permitido por
  PROJECT_SPEC.md §6.5.

Erros seguem o envelope JSON-RPC 2.0 padrão (`{"error": {"code", "message"}}`).

## MCP

Implementado para o Flight Agent (`mcp/flight-search`, Streamable HTTP,
`POST /mcp`, tool `search_flights`), usando o SDK oficial `mcp` (Python).
`MOCK_MODE=true` por padrão (§23) — dados determinísticos, sem API paga.
Hotel/Places/Weather/Currency/Calculator ainda não implementados
(Fases 3-5).

## HTTP / Health

Todo serviço expõe:

- `GET /health` — processo vivo.
- `GET /ready` — dependências essenciais (ex.: registry) alcançáveis.
