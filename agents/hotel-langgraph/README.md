# hotel-agent

Especialista em hotéis (LangGraph, TypeScript), conforme
`PROJECT_SPEC.md` §5.3. Primeiro agente não-Python da POC — prova que o
protocolo A2A (não uma biblioteca compartilhada) é o que garante
interoperabilidade entre o Planner (Python) e este agente (Node.js).

## Fluxo com estado (LangGraph)

```text
parse_request
      ↓
search_hotels
      ↓
filter_results
      ↓
rank_results
      ↓
build_response
```

- `parse_request`: valida destino, datas, hóspedes (campos mínimos do §5.3).
- `search_hotels`: chama `mcp-hotel-search` via MCP.
- `filter_results`: descarta hotéis cujo custo total (diária × noites)
  excede o orçamento informado, quando houver.
- `rank_results`: ordena por avaliação (desc), preço como desempate,
  limita a 5 opções.
- `build_response`: monta o `HotelResult` final.

Nunca inventa dados de hotel (§31): qualquer falha do MCP ou critério não
atendido resulta em `status: UNAVAILABLE`, nunca em um palpite.

## Endpoints

- `GET /health`, `GET /ready`
- `GET /.well-known/agent-card.json`
- `POST /a2a` (skill `search_hotels`) — mesmo protocolo JSON-RPC 2.0 dos
  agentes Python (`message/send`, `tasks/get`, `tasks/cancel`), implementado
  em `src/a2a/` como espelho TypeScript do adapter Python
  (ver `docs/adr/ADR-008-custom-a2a-adapter.md`).

## Rodando localmente

```bash
npm install
MCP_HOTEL_URL=http://localhost:9002/mcp PORT=8003 npm start
```

## Testes

```bash
npm test
```
