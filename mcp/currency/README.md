# mcp-currency

Servidor MCP (Streamable HTTP, `/mcp`) com uma tool: `convert_currency`.
Consumido pelo `budget-agent` (`agents/budget-crewai`).

## Tool

```json
{
  "amount": 1000,
  "from_currency": "BRL",
  "to_currency": "USD"
}
```

Retorna conversão determinística usando uma tabela de câmbio fixa e
ilustrativa (não é uma cotação em tempo real — nenhuma API paga foi
especificada, e `PROJECT_SPEC.md` §31 proíbe inventar dados que
aparentem ser reais). Moedas suportadas: `BRL`, `USD`, `EUR`, `GBP`,
`ARS`, `CLP`.

## Endpoints

- `GET /health`, `GET /ready`
- `POST /mcp` (MCP Streamable HTTP)

## Rodando localmente

```bash
pip install -r requirements.txt
python -m app.server
```
