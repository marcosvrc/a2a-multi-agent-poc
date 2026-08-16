# mcp-calculator

Servidor MCP (Streamable HTTP, `/mcp`) com quatro tools binárias: `sum`,
`subtract`, `multiply`, `divide`. Consumido pelo `budget-agent`
(`agents/budget-crewai`).

Cada tool executa exatamente uma operação aritmética fixa sobre dois
números (`a`, `b`). Não há tool de avaliação de expressão livre, e nenhum
`eval`/`exec` é usado neste servidor — restrição explícita do
`PROJECT_SPEC.md` §33 ("Não permitir expressão arbitrária executada via
eval"). `divide` por zero retorna `{"result": null, "error": "..."}` em
vez de lançar exceção.

## Endpoints

- `GET /health`, `GET /ready`
- `POST /mcp` (MCP Streamable HTTP)

## Rodando localmente

```bash
pip install -r requirements.txt
python -m app.server
```
