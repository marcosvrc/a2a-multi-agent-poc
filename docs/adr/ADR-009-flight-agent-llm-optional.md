# ADR-009 — Flight Agent: caminho determinístico por padrão, LLM opcional

## Status
Aceito

## Contexto
PROJECT_SPEC.md §5.2 exige o Flight Agent em OpenAI Agents SDK. RNF-03
exige que o modo padrão não exija nenhuma API paga (incluindo OpenAI).
Essas duas exigências só coexistem se a camada de raciocínio via LLM for
opcional.

## Decisão
`agents/flight-openai` implementa dois caminhos:

- **Determinístico (padrão, sem `OPENAI_API_KEY`)**: chama
  `mcp-flight-search` diretamente, ordena por preço, retorna até 5 opções.
  É o caminho testado automaticamente (`tests/`) e o que roda em
  `docker compose up` sem custo.
- **Guiado por LLM (`OPENAI_API_KEY` setada)**: usa `agents.Agent` +
  `agents.Runner` do OpenAI Agents SDK, com o prompt de `app/prompts.py`
  (idêntico ao exemplo do §29) e o MCP como *function tool*. Qualquer
  falha nesse caminho cai automaticamente para o determinístico.

Em ambos os casos, nenhum preço é inventado (§31): toda opção retornada
vem de uma chamada real a `search_flights` via MCP.

## Consequências
- O caminho guiado por LLM não é exercitado pelos testes automatizados
  desta milestone (nenhuma `OPENAI_API_KEY` disponível no ambiente de
  desenvolvimento). Antes de depender dele, validar manualmente com uma
  chave real.
- O contrato A2A (`search_flights` skill, mensagem de entrada/saída) é o
  mesmo nos dois caminhos — trocar de determinístico para LLM não quebra
  o Planner nem os testes de contrato.
