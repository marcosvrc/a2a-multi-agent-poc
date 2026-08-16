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

## Addendum — bug encontrado ao validar manualmente (exatamente o alerta acima)

Ao testar o caminho guiado pela primeira vez com uma chave real, o modelo
devolveu `"status": "OK"` em vez de um dos quatro valores do enum
(`SUCCESS`/`PARTIAL`/`UNAVAILABLE`/`UNKNOWN`). Como `_search_via_llm`
repassava o JSON do modelo sem validar nada, o erro só aparecia lá na
frente, como `pydantic.ValidationError` do lado do Planner
(`agents/planner-adk/app/schemas.py::SubResult`) — derrubando a requisição
inteira em vez de degradar de forma isolada, como o Activity/BeeAI e o
Budget/CrewAI já faziam.

Corrigido em duas frentes: (1) `app/prompts.py::FLIGHT_PROMPT` agora lista
explicitamente os quatro valores aceitos para `status`, deixando claro que
qualquer outro é rejeitado; (2) `app/agent.py::_search_via_llm` valida o
`status` da resposta contra `VALID_STATUSES` antes de devolvê-la — se vier
fora do enum, levanta `ValueError`, que `build_flight_result` já captura e
usa para cair no caminho determinístico (mesmo padrão de fallback dos
outros dois agentes opcionais).

Dois testes novos (`agents/flight-openai/tests/test_agent.py`) travam essa
regressão, usando a mesma técnica de stub em `sys.modules["agents"]` já
usada para `crewai`/`beeai_framework`: `test_llm_invalid_status_falls_back_to_deterministic`
(um `status: "OK"` simulado cai no determinístico) e
`test_llm_valid_status_is_returned_as_is` (um `status` válido passa
direto, sem esse guard interferir no caminho feliz).
