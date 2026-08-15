# ADR-002 — Usar MCP para integração Agent-to-Tool

## Status
Aceito

## Contexto
Ferramentas, APIs externas e fontes de dados reutilizáveis não devem ser
duplicadas em cada agente (PROJECT_SPEC.md §1, item 2).

## Decisão
Toda integração externa reutilizável (busca de voos, hotéis, lugares,
clima, câmbio, cálculo) é exposta como um servidor MCP dedicado
(`mcp/flight-search`, `mcp/hotel-search`, `mcp/places`, `mcp/weather`,
`mcp/currency`, `mcp/calculator`), consumido pelos agentes especialistas
via MCP 2026-07-28 (com fallback de versão quando necessário).

## Consequências
- Os servidores MCP ainda não foram implementados nesta milestone (M1);
  serão adicionados junto de cada especialista (Fases 2-5, ver
  `docs/architecture.md`).
- Todos os MCP servers devem suportar `MOCK_MODE=true` (§23).
