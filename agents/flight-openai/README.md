# flight-agent

Especialista em voos (OpenAI Agents SDK, Python), conforme
`PROJECT_SPEC.md` §5.2. Consome `mcp-flight-search` via MCP, nunca inventa
preços (§31), expõe a skill A2A `search_flights`.

## Dois caminhos de execução

- **Determinístico (padrão)**: sem `OPENAI_API_KEY`, chama o MCP
  diretamente e ordena por preço. É o caminho testado automaticamente e
  o que roda em `docker compose up` sem custo (RNF-03).
- **Guiado por LLM (opcional)**: se `OPENAI_API_KEY` estiver setada, usa
  `agents.Agent` + `agents.Runner` (OpenAI Agents SDK) com o prompt em
  `app/prompts.py`, chamando o MCP como *function tool*. Se a chamada ao
  LLM falhar por qualquer motivo, cai automaticamente para o caminho
  determinístico. **Este caminho não é exercitado pelos testes
  automatizados** (nenhuma chave de API está disponível no ambiente de
  desenvolvimento/CI desta milestone) — validar manualmente antes de
  depender dele em produção.

## Endpoints

- `GET /health`, `GET /ready`
- `GET /.well-known/agent-card.json`
- `POST /a2a` (skill `search_flights`)

## Protocolo de mensagem A2A

Entrada (`message/send`, texto = JSON):
```json
{"origin": "GRU", "destination": "FLN", "start_date": "2026-09-20", "end_date": "2026-09-24", "travelers": 2}
```

Saída (texto da resposta = JSON `FlightResult`, ver
`contracts/schemas/flight-result.schema.json`).

## Rodando localmente

```bash
pip install -e .
MCP_FLIGHT_URL=http://localhost:9001 uvicorn app.main:app --reload --port 8002
```
