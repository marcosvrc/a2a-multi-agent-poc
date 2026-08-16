# Protocolos

## A2A (implementado nesta milestone via adapter próprio)

Ver ADR-008 para a justificativa de não usar o `a2a-sdk` oficial ainda.
Implementado duas vezes, independentemente: uma vez em Python
(`agents/*/app/a2a/`, usada por planner-agent, flight-agent,
activity-agent e mock-specialist-agent — cada agente tem sua própria
cópia do adapter, não um pacote compartilhado, per §42 regra 6) e uma vez
em TypeScript (`agents/hotel-langgraph/src/a2a/`, usada pelo hotel-agent)
— mesmo contrato de wire, sem código compartilhado entre as duas
linguagens (ver ADR-010).

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
`POST /mcp`, tool `search_flights`, SDK oficial `mcp` em Python), para o
Hotel Agent (`mcp/hotel-search`, Streamable HTTP, `POST /mcp`, tool
`search_hotels`, também SDK oficial `mcp` em Python — o servidor MCP em si
não precisa ser reimplementado por linguagem, apenas o *cliente* MCP
dentro do hotel-agent, que é TypeScript via `@modelcontextprotocol/sdk`,
ver `agents/hotel-langgraph/src/mcpClient.ts`) e para o Activity Agent
(`mcp/places`, tool `search_places`, e `mcp/weather`, tool `get_weather`
— ambos Streamable HTTP, SDK oficial `mcp`, consumidos pelo mesmo cliente
genérico `agents/activity-beeai/app/mcp_client.py::call_mcp_tool`).
`MOCK_MODE=true` por padrão (§23) — dados determinísticos, sem API paga.
Currency/Calculator ainda não implementados (Fase 5).

## HTTP / Health

Todo serviço expõe:

- `GET /health` — processo vivo.
- `GET /ready` — dependências essenciais (ex.: registry) alcançáveis.
