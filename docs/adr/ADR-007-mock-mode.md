# ADR-007 — Mock Mode obrigatório

## Status
Aceito

## Contexto
A POC precisa rodar sem APIs comerciais, para CI, desenvolvimento local,
demos e testes de contrato (PROJECT_SPEC.md §23).

## Decisão
`MOCK_MODE=true` é o padrão em `.env.example`. Os servidores MCP (a serem
implementados nas Fases 2-5) devem retornar dados determinísticos nesse
modo. Nesta milestone, o `mock-specialist-agent` já segue esse princípio:
resposta 100% determinística, sem dependências externas.

## Consequências
- Nenhuma chave de API é necessária para rodar `make local` nesta
  milestone.
